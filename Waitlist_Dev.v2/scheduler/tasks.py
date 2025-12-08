from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from pilot_data.models import EveCharacter, EsiHeaderCache
from esi_calls.token_manager import update_character_data
import logging
from django.db.models import Q

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
    
    # --- STRATEGY 1: Safety Net (PRIORITY FIX) ---
    # We run this FIRST to catch broken characters before the cache logic sees them.
    
    # 1. Define "Broken" (Missing Critical Data)
    # We allow a 5-minute grace period for new characters to settle.
    creation_grace = now - timedelta(minutes=5)
    
    # 2. Define "Stale" (Hasn't updated in 24h)
    stale_threshold = now - timedelta(hours=24)
    
    broken_chars = EveCharacter.objects.filter(
        # Condition A: It's old enough to have data, but doesn't (Missing Corp OR Zero SP)
        (Q(last_updated__lt=creation_grace) & (Q(total_sp=0) | Q(corporation_name=""))) |
        
        # Condition B: It hasn't been updated in 24 hours
        Q(last_updated__lt=stale_threshold) |
        
        # Condition C: It has NEVER been updated (and is older than grace period)
        (Q(last_updated__isnull=True) & Q(id__gt=0)) # id check is just a dummy true
    ).values_list('character_id', flat=True)

    if broken_chars:
        count = len(broken_chars)
        logger.warning(f"[Dispatcher] Safety Net: Found {count} broken/stale characters. Forcing FULL refresh.")
        
        for char_id in broken_chars:
            # Force Full Refresh (target_endpoints=None, force_refresh=True)
            refresh_character_task.delay(char_id, None, force_refresh=True)
            processed_ids.add(char_id)
            tasks_queued += 1

    # --- STRATEGY 2: Cache Expiry (Standard Maintenance) ---
    # Only process characters we haven't already fixed in Step 1
    expired_headers = EsiHeaderCache.objects.filter(expires__lte=now).select_related('character')
    updates_map = {}

    for header in expired_headers:
        char = header.character
        char_id = char.character_id
        
        # Skip if already handled by Safety Net
        if char_id in processed_ids:
            continue
            
        endpoint = header.endpoint_name
        
        if not char.is_online:
            if endpoint != 'online':
                time_since_expiry = now - header.expires
                if time_since_expiry < OFFLINE_THROTTLE_WINDOW:
                    continue

        if char_id not in updates_map:
            updates_map[char_id] = []
        updates_map[char_id].append(endpoint)

    if updates_map:
        logger.info(f"[Dispatcher] Found {len(updates_map)} characters with expired caches.")
        for char_id, endpoints in updates_map.items():
            # Standard Partial Update (Use Cache)
            refresh_character_task.delay(char_id, endpoints, force_refresh=False)
            tasks_queued += 1

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
        
        mode_str = "FULL UPDATE" if target_endpoints is None else f"Partial: {target_endpoints}"
        if force_refresh: mode_str += " (FORCED)"
        
        # Log if it's substantial work
        if target_endpoints != ['online']:
            logger.info(f"[Worker] Updating {char.character_name} [{mode_str}]")
        
        # Pass force_refresh to manager
        success = update_character_data(char, target_endpoints, force_refresh=force_refresh)
        
        if not success:
            logger.warning(f"[Worker] Failed to update: {char.character_name}")
            # Bump timestamp slightly to prevent immediate loop, but ensure retry
            char.last_updated = timezone.now()
            char.save(update_fields=['last_updated'])

    except EveCharacter.DoesNotExist:
        logger.error(f"[Worker] Character ID {char_id} not found.")
    except Exception as e:
        logger.error(f"[Worker] Crash on {char_id}: {e}")