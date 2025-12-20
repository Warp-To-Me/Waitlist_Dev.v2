from django.dispatch import receiver
from esi.signals import esi_request_statistics
from django.core.cache import cache
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import asyncio
import logging

logger = logging.getLogger(__name__)

@receiver(esi_request_statistics)
def log_esi_statistics(sender, operation, status_code, latency, **kwargs):
    """
    Listens to ESI requests and logs errors or slow requests.
    Note: This signal does not provide user context, so it is used for system monitoring only.
    """
    if status_code >= 400:
        logger.warning(f"ESI Error {status_code} on {operation} ({latency:.2f}s)")

def notify_user_ratelimit(user, headers):
    """
    Helper to parse Rate Limit headers and push a notification to the user's WebSocket.
    Can be called manually from views or tasks where the user context is known.
    """
    if not user or not user.is_authenticated:
        return

    # Cache throttle to prevent spamming the user
    cache_key = f"broadcast_throttle_{user.id}"
    if cache.get(cache_key):
        return
    cache.set(cache_key, True, timeout=2)

    remaining = headers.get('X-Ratelimit-Remaining')
    limit_str = headers.get('X-Ratelimit-Limit')
    bucket_group = headers.get('X-Ratelimit-Group', 'default')
    esi_remain = headers.get('X-Esi-Error-Limit-Remain')
    
    payload = None

    if remaining and limit_str:
        try:
            limit_val, window_str = limit_str.split('/')
            limit_val = int(limit_val)
            payload = {
                'type': 'ratelimit',
                'bucket': bucket_group,
                'remaining': int(remaining),
                'limit': limit_val,
                'window': window_str
            }
        except ValueError:
            pass
            
    elif esi_remain:
        payload = {
            'type': 'ratelimit',
            'bucket': 'Global Error',
            'remaining': int(esi_remain),
            'limit': 100, 
            'window': '60s'
        }

    if payload:
        channel_layer = get_channel_layer()
        # Safe async dispatch that handles both Sync (Thread) and Async (Event Loop) contexts
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(channel_layer.group_send(
                f"user_{user.id}",
                {"type": "user_notification", "data": payload}
            ))
        except RuntimeError:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {"type": "user_notification", "data": payload}
            )
