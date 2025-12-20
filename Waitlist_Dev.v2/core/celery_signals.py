from celery.signals import task_prerun, task_postrun
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import time

logger = logging.getLogger(__name__)

# Helper to broadcast
def broadcast_celery_event(event_type, task_data):
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "system",
                {
                    "type": "celery_task_update",
                    "data": {
                        "type": "celery_task_update",
                        "event": event_type,
                        "task": task_data
                    }
                }
            )
    except Exception as e:
        # Don't crash the task if websocket fails
        logger.error(f"Failed to broadcast celery event: {e}")

@task_prerun.connect
def on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **opts):
    """
    Fired when a task starts.
    """
    if not task: return

    # Enrich args for display if possible (similar to utils.py logic)
    enriched_info = ""
    enriched_name = ""

    # Check if this is a refresh_character task
    if 'refresh_character' in task.name:
        try:
            char_id = args[0] if args else None
            # Lazy import to avoid circular dependency if possible, or just skip name resolution for speed
            # Since this runs INSIDE the worker, we can assume DB access is fine if configured.
            # But resolving every name might be heavy? Let's try to resolve if simple.
            from pilot_data.models import EveCharacter
            try:
                c = EveCharacter.objects.get(character_id=char_id)
                enriched_name = c.character_name
            except:
                enriched_name = f"ID: {char_id}"

            endpoints = args[1] if len(args) > 1 else None
            force = args[2] if len(args) > 2 else False

            if force: enriched_info += "[FORCED] "
            if endpoints is None:
                enriched_info += "Full Update"
            else:
                enriched_info += f"Partial: {endpoints}"
        except:
            pass

    task_data = {
        "id": task_id,
        "name": task.name,
        "args": str(args),
        "kwargs": str(kwargs),
        "worker": sender.request.hostname if sender and hasattr(sender, 'request') else "Unknown",
        "timestamp": time.time(),
        "enriched_name": enriched_name,
        "enriched_info": enriched_info
    }

    broadcast_celery_event("started", task_data)

@task_postrun.connect
def on_task_postrun(sender=None, task_id=None, task=None, state=None, retval=None, **kwargs):
    """
    Fired when a task ends.
    """
    task_data = {
        "id": task_id,
        "state": state,
        "timestamp": time.time(),
        # We don't send retval to avoid leaking data or large payloads
    }
    broadcast_celery_event("finished", task_data)
