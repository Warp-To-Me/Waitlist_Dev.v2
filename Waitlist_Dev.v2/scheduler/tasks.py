from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from pilot_data.models import EveCharacter, EsiHeaderCache
from esi_calls.token_manager import update_character_data
import logging

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# TASK 1: THE SMART DISPATCHER
# Runs every 1 minute (via Celery Beat)
# ----------------------------------------------------------------------
@shared_task
def dispatch_stale_characters():
    """
    Intelligent Dispatcher that:
    1. Checks EsiHeaderCache for expired endpoints.
    2. Groups them by Character.
    3. Queues tasks only for specific endpoints that need refreshing.
    4. THROTTLES offline characters to reduce load.
    5. Fallback: Checks for characters that have NEVER been updated.
    """
    now = timezone.now()
    tasks_queued = 0
    
    # Define the "Grace Period" for offline characters (15 Minutes)
    OFFLINE_THROTTLE_WINDOW = timedelta(minutes=15)

    # --- STRATEGY 1: Cache Expiry (The Happy Path) ---
    # Find all cache entries that have expired
    expired_headers = EsiHeaderCache.objects.filter(
        expires__lte=now
    ).select_related('character')

    # Group by Character ID
    updates_map = {}

    for header in expired_headers:
        char = header.character
        char_id = char.character_id
        endpoint = header.endpoint_name
        
        # --- OFFLINE THROTTLE LOGIC ---
        if not char.is_online:
            # RULE 1: Always allow the 'online' endpoint to run immediately
            # This ensures we detect when they log in without delay.
            if endpoint != 'online':
                
                # RULE 2: For other endpoints, check how long they have been expired.
                # If they expired recently, we SKIP them to save resources.
                # We wait until they have been expired for at least 15 minutes.
                time_since_expiry = now - header.expires
                
                if time_since_expiry < OFFLINE_THROTTLE_WINDOW:
                    # Too soon. Let it "ripen" a bit longer.
                    continue

        if char_id not in updates_map:
            updates_map[char_id] = []
        updates_map[char_id].append(endpoint)

    # Queue Tasks for Expired Items
    if updates_map:
        logger.info(f"[Dispatcher] Found {len(updates_map)} characters with expired caches.")
        for char_id, endpoints in updates_map.items():
            refresh_character_task.delay(char_id, endpoints)
            tasks_queued += 1

    # --- STRATEGY 2: Safety Net (The "Lost" Characters) ---
    # Characters that have NO cache entries (freshly added) OR 
    # haven't updated in 24 hours (potential stuck tasks/errors).
    
    # 2a. Never updated
    fresh_chars = EveCharacter.objects.filter(last_updated__isnull=True).values_list('character_id', flat=True)
    
    # 2b. Stuck/Broken (No update in 24h)
    stale_threshold = now - timedelta(hours=24)
    stale_chars = EveCharacter.objects.filter(last_updated__lt=stale_threshold).values_list('character_id', flat=True)

    # Combine sets
    force_update_ids = set(fresh_chars) | set(stale_chars)
    
    # Remove any we already queued in Strategy 1 to avoid double work
    force_update_ids = force_update_ids - set(updates_map.keys())

    if force_update_ids:
        logger.warning(f"[Dispatcher] Safety Net: Forcing update on {len(force_update_ids)} stale/empty characters.")
        for char_id in force_update_ids:
            refresh_character_task.delay(char_id, None)
            tasks_queued += 1

    logger.info(f"[Dispatcher] Cycle Complete. Total Tasks Queued: {tasks_queued}")

# ----------------------------------------------------------------------
# TASK 2: THE WORKER
# ----------------------------------------------------------------------
@shared_task(rate_limit='300/m')
def refresh_character_task(char_id, target_endpoints=None):
    """
    Refreshes a single character.
    :param char_id: EVE Character ID
    :param target_endpoints: List of endpoint names (strings) or None for ALL.
    """
    try:
        char = EveCharacter.objects.get(character_id=char_id)
        
        mode_str = "FULL UPDATE" if target_endpoints is None else f"Partial: {target_endpoints}"
        # Only log if it's NOT just an online check (reduce log noise)
        if target_endpoints != ['online']:
            logger.info(f"[Worker] Updating {char.character_name} [{mode_str}]")
        
        success = update_character_data(char, target_endpoints)
        
        if not success:
            logger.warning(f"[Worker] Failed to update: {char.character_name}")
            # Bump timestamp to prevent immediate Safety Net requeue
            char.last_updated = timezone.now()
            char.save(update_fields=['last_updated'])

    except EveCharacter.DoesNotExist:
        logger.error(f"[Worker] Character ID {char_id} not found.")
    except Exception as e:
        logger.error(f"[Worker] Crash on {char_id}: {e}")