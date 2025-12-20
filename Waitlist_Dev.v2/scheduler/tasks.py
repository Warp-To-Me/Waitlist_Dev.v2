from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
import logging

# Models
from pilot_data.models import EveCharacter, EsiHeaderCache, SRPConfiguration
from esi_calls.token_manager import update_character_data
from esi_calls.wallet_service import sync_corp_wallet
from esi.models import Token # Import ESI Token

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# TASK 1: THE SMART DISPATCHER
# ----------------------------------------------------------------------
@shared_task
def dispatch_stale_characters():
    now = timezone.now()
    tasks_queued = 0
    processed_ids = set() # Track characters we have already queued
    
    STALE_THRESHOLD = timedelta(hours=24) # 24h Stale Definition
    
    # --- STRATEGY 1: Stale / Broken (PRIORITY FIX) ---
    # We run this FIRST to catch broken characters before the cache logic sees them.
    
    # 1. Define "Broken" (Missing Critical Data)
    creation_grace = now - timedelta(minutes=5)
    
    # 2. Define "Stale" (Hasn't updated in 24h)
    stale_limit = now - STALE_THRESHOLD
    
    broken_chars = EveCharacter.objects.filter(
        # Condition A: It's old enough to have data, but doesn't
        (Q(last_updated__lt=creation_grace) & (Q(total_sp=0) | Q(corporation_name=""))) |
        # Condition B: Emergency fallback if nothing ran for 24h
        Q(last_updated__lt=stale_limit) |
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

    # --- STRATEGY 2: Cache Expiry ---
    # Only process characters we haven't already fixed in Step 1
    expired_headers = EsiHeaderCache.objects.filter(expires__lte=now).select_related('character')
    updates_map = {}

    for header in expired_headers:
        char = header.character
        char_id = char.character_id
        
        # Skip if already handled
        if char_id in processed_ids:
            continue
            
        endpoint = header.endpoint_name
        
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
                    # Skip deprecated 'online' endpoint
                    if ep == 'online':
                        continue

                    # Map endpoint to scope
                    scope_needed = None
                    if ep == 'wallet': scope_needed = 'esi-wallet.read_character_wallet.v1'
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

                    # CLAIM: Bump expiry by 10 minutes to prevent re-queuing while task is pending/running
                    # If the task succeeds, it will overwrite this with the real ESI expiry (e.g. +1h)
                    EsiHeaderCache.objects.filter(
                        character_id=char_id,
                        endpoint_name__in=valid_endpoints
                    ).update(expires=now + timedelta(minutes=10))

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
        
        # Pass force_refresh to manager (which uses call_esi which uses esi.Token)
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
