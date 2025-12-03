from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from pilot_data.models import EveCharacter
from esi_calls.token_manager import update_character_data
import logging

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# TASK 1: THE DISPATCHER (The Boss)
# Runs every 15 minutes (via Celery Beat)
# ----------------------------------------------------------------------
@shared_task
def dispatch_stale_characters():
    """
    Finds characters not updated in 60 minutes and queues them for refresh.
    """
    threshold = timezone.now() - timedelta(minutes=60)
    
    # NOTE: We removed the limit of [:50]. 
    # Since we are async now, we can queue 1000s of tasks if needed.
    # We only fetch the ID to keep memory usage low.
    stale_ids = EveCharacter.objects.filter(
        last_updated__lt=threshold
    ).values_list('character_id', flat=True)

    count = len(stale_ids)
    if count > 0:
        logger.info(f"[Dispatcher] Found {count} stale characters. Queuing tasks...")
        
        for char_id in stale_ids:
            # Send to the queue. 
            refresh_character_task.delay(char_id)
            
    else:
        logger.info("[Dispatcher] No stale characters found.")

# ----------------------------------------------------------------------
# TASK 2: THE WORKER (The Employee)
# Picked up by Celery Workers
# ----------------------------------------------------------------------
# RATE LIMIT PROTECTION:
# rate_limit='50/m' ensures THIS specific task is not executed more than 
# 50 times per minute per worker node. This prevents the "Fire Hose" effect.
@shared_task(rate_limit='300/m')
def refresh_character_task(char_id):
    """
    Refreshes a single character.
    """
    try:
        # Re-fetch character from DB to ensure we have latest data
        char = EveCharacter.objects.get(character_id=char_id)
        
        logger.info(f"[Worker] Updating {char.character_name}...")
        
        success = update_character_data(char)
        
        if success:
            logger.info(f"[Worker] Success: {char.character_name}")
        else:
            logger.warning(f"[Worker] Failed to update: {char.character_name}")
            # IMPORTANT: We still touch last_updated in the token_manager or here
            # to prevent immediate re-queueing by the dispatcher in 15 mins.
            char.last_updated = timezone.now()
            char.save(update_fields=['last_updated'])

    except EveCharacter.DoesNotExist:
        logger.error(f"[Worker] Character ID {char_id} not found.")
    except Exception as e:
        logger.error(f"[Worker] Crash on {char_id}: {e}")