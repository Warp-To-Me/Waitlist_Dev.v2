from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
import logging

# Models
from pilot_data.models import EveCharacter, EsiHeaderCache, SRPConfiguration
from esi_calls.token_manager import update_character_data
from esi_calls.wallet_service import sync_corp_wallet

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# TASK 1: THE SMART DISPATCHER
# ----------------------------------------------------------------------
@shared_task
def dispatch_stale_characters():
    now = timezone.now()
    tasks_queued = 0
    processed_ids = set() # Track characters we have already queued
    
    OFFLINE_THROTTLE_WINDOW = timedelta(minutes=15)
    INACTIVE_SNAPSHOT_WINDOW = timedelta(hours=48) # 48h Snapshot
    
    # --- STRATEGY 1: Safety Net (PRIORITY FIX) ---
    # We run this FIRST to catch broken characters before the cache logic sees them.
    
    # 1. Define "Broken" (Missing Critical Data)
    creation_grace = now - timedelta(minutes=5)
    
    # 2. Define "Stale" (Hasn't updated in 48h - fallback)
    stale_threshold = now - timedelta(hours=48)
    
    broken_chars = EveCharacter.objects.filter(
        # Condition A: It's old enough to have data, but doesn't
        (Q(last_updated__lt=creation_grace) & (Q(total_sp=0) | Q(corporation_name=""))) |
        # Condition B: Emergency fallback if nothing ran for 2 days
        Q(last_updated__lt=stale_threshold) |
        # Condition C: Never updated
        (Q(last_updated__isnull=True) & Q(id__gt=0))
    ).values_list('character_id', flat=True)

    if broken_chars:
        count = len(broken_chars)
        logger.warning(f"[Dispatcher] Safety Net: Found {count} broken/stale characters. Forcing FULL refresh.")
        
        for char_id in broken_chars:
            refresh_character_task.delay(char_id, None, force_refresh=True)
            processed_ids.add(char_id)
            tasks_queued += 1

    # --- STRATEGY 2: Inactive "Heartbeat" (Keep Token Alive + Skill History) ---
    # If a character is OFFLINE and hasn't been updated in 48 hours,
    # we trigger a specific update for Skills/History.
    # This implicitly refreshes the Auth Token, keeping it valid.
    
    heartbeat_chars = EveCharacter.objects.filter(
        is_online=False,
        last_updated__lt=now - INACTIVE_SNAPSHOT_WINDOW
    ).exclude(character_id__in=processed_ids).values_list('character_id', flat=True)

    if heartbeat_chars:
        count = len(heartbeat_chars)
        logger.info(f"[Dispatcher] Heartbeat: Queueing snapshot for {count} inactive pilots.")
        
        for char_id in heartbeat_chars:
            # We ONLY pull persistent data. We SKIP location/ship to save ESI calls.
            # check_token() inside this task will refresh the auth token automatically.
            refresh_character_task.delay(char_id, ['skills', 'queue', 'history', 'public_info'])
            processed_ids.add(char_id)
            tasks_queued += 1

    # --- STRATEGY 3: Cache Expiry (Active & Online Monitoring) ---
    # Only process characters we haven't already fixed in Step 1 or 2
    expired_headers = EsiHeaderCache.objects.filter(expires__lte=now).select_related('character')
    updates_map = {}

    for header in expired_headers:
        char = header.character
        char_id = char.character_id
        
        # Skip if already handled
        if char_id in processed_ids:
            continue
            
        endpoint = header.endpoint_name
        
        # Check if character is offline AND outside the grace period
        is_recently_online = False
        if char.last_online_at:
            if now - char.last_online_at < OFFLINE_THROTTLE_WINDOW:
                is_recently_online = True

        if not char.is_online and not is_recently_online:
            # If Offline and NOT recently online, we only check the 'online' endpoint to see if they came back.
            # We do NOT check other endpoints (ship, wallet) until they wake up.
            if endpoint != 'online':
                # Apply throttle window to prevent spamming /online/ check too fast
                # Note: The 'online' endpoint usually has a 60s cache, but we rely on
                # EsiHeaderCache to tell us when that 60s is up.
                continue
            
            # Additional safety: Don't check /online/ more than every 15m for offline users
            # (Unless the cache header explicitly says otherwise, but we enforce a minimum)
            time_since_last = now - (char.last_updated or (now - timedelta(days=1)))
            if time_since_last < OFFLINE_THROTTLE_WINDOW:
                continue

        if char_id not in updates_map:
            updates_map[char_id] = []
        updates_map[char_id].append(endpoint)

    if updates_map:
        # logger.info(f"[Dispatcher] Found {len(updates_map)} characters with expired caches.")
        for char_id, endpoints in updates_map.items():
            # Retrieve character to check scopes
            try:
                char_obj = EveCharacter.objects.get(character_id=char_id)
                granted = set(char_obj.granted_scopes.split()) if char_obj.granted_scopes else None

                # Filter endpoints based on scopes
                valid_endpoints = []
                for ep in endpoints:
                    # Map endpoint to scope
                    scope_needed = None
                    if ep == 'wallet': scope_needed = 'esi-wallet.read_character_wallet.v1'
                    elif ep == 'online': scope_needed = 'esi-location.read_online.v1'
                    elif ep == 'ship': scope_needed = 'esi-location.read_ship_type.v1'
                    elif ep == 'lp': scope_needed = 'esi-characters.read_loyalty.v1'
                    # Base scopes (skills, queue, implants) are usually assumed present

                    if granted is None:
                        # Legacy/No scopes recorded -> Allow for now or Block?
                        # Let's allow for backwards compatibility unless strict
                        valid_endpoints.append(ep)
                    elif scope_needed and scope_needed not in granted:
                        continue # Skip this endpoint
                    else:
                        valid_endpoints.append(ep)

                if valid_endpoints:
                    refresh_character_task.delay(char_id, valid_endpoints, force_refresh=False)
                    tasks_queued += 1

            except EveCharacter.DoesNotExist:
                continue

    if tasks_queued > 0:
        logger.info(f"[Dispatcher] Cycle Complete. Total Tasks Queued: {tasks_queued}")

# ----------------------------------------------------------------------
# TASK 2: THE WORKER
# ----------------------------------------------------------------------
@shared_task(rate_limit='300/m')
def refresh_character_task(char_id, target_endpoints=None, force_refresh=False):
    """
    Refreshes a single character.
    """
    try:
        char = EveCharacter.objects.get(character_id=char_id)
        
        # Log Logic: Reduce spam by only logging "Real" updates
        is_heartbeat = target_endpoints and 'skills' in target_endpoints and 'ship' not in target_endpoints
        is_online_check = target_endpoints == ['online']
        
        if not is_online_check:
            mode_str = "FULL" if target_endpoints is None else f"Partial: {len(target_endpoints)}"
            if is_heartbeat: mode_str = "HEARTBEAT"
            logger.info(f"[Worker] Updating {char.character_name} [{mode_str}]")
        
        # Pass force_refresh to manager
        success = update_character_data(char, target_endpoints, force_refresh=force_refresh)
        
        if not success:
            # On failure, bump timestamp slightly to prevent immediate loop, but ensure retry
            char.last_updated = timezone.now()
            char.save(update_fields=['last_updated'])

    except EveCharacter.DoesNotExist:
        logger.error(f"[Worker] Character ID {char_id} not found.")
    except Exception as e:
        logger.error(f"[Worker] Crash on {char_id}: {e}")

# --- NEW: SRP WALLET SYNC TASK ---
@shared_task(bind=True, max_retries=3)
def refresh_srp_wallet_task(self):
    """
    Background task to sync Corporation Wallet Journal.
    Runs hourly via Beat or manually via Button.
    """
    try:
        config = SRPConfiguration.objects.first()
        if not config or not config.is_active:
            logger.info("[SRP] No active configuration found. Skipping sync.")
            return "No Config"

        logger.info(f"[SRP] Starting Wallet Sync via {config.character.character_name}...")
        
        success, msg = sync_corp_wallet(config)
        
        if success:
            logger.info(f"[SRP] Sync Complete: {msg}")
            return f"Success: {msg}"
        else:
            logger.warning(f"[SRP] Sync Failed: {msg}")
            # Optional: Retry on specific errors if needed
            return f"Failed: {msg}"

    except Exception as e:
        logger.error(f"[SRP] Critical Error: {str(e)}")
        # Raise to let Celery know it failed
        raise e