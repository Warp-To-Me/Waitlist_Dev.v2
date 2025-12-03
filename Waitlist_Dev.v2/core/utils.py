import redis
import time
from django.conf import settings
from waitlist_project.celery import app as celery_app

def get_system_status():
    """
    Fetches Redis connection status, Queue depth, and Celery Worker inspection data.
    Returns a dictionary context suitable for template rendering.
    """
    # 1. Check Redis Connection & Queue Depth
    redis_status = "OFFLINE"
    redis_error = None
    queue_length = 0
    redis_latency = 0
    
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        start_time = time.time()
        r.ping()
        redis_latency = int((time.time() - start_time) * 1000)
        
        # 'celery' is the default queue name.
        queue_length = r.llen('celery')
        redis_status = "ONLINE"
    except Exception as e:
        redis_error = str(e)

    # 2. Inspect Celery Workers
    # Set a timeout (0.5s) to ensure the dashboard remains snappy
    inspector = celery_app.control.inspect(timeout=0.5)
    
    workers = {}
    active_tasks = {}
    reserved_tasks = {}
    stats = {}
    total_processed = 0

    try:
        # Pinging workers to see who is alive
        workers_ping = inspector.ping()
        if workers_ping:
            workers = workers_ping
            active_tasks = inspector.active() or {}
            reserved_tasks = inspector.reserved() or {}
            stats = inspector.stats() or {}
    except Exception as e:
        if not redis_error:
            redis_error = f"Celery Inspect Error: {str(e)}"

    # Organize data
    worker_data = []
    if workers:
        for worker_name, response in workers.items():
            w_active = active_tasks.get(worker_name, [])
            w_reserved = reserved_tasks.get(worker_name, [])
            w_stats = stats.get(worker_name, {})
            
            w_total = sum(w_stats.get('total', {}).values())
            total_processed += w_total
            
            worker_data.append({
                'name': worker_name,
                'status': 'Active' if response.get('ok') == 'pong' else 'Unknown',
                'active_count': len(w_active),
                'active_tasks': w_active,
                'reserved_count': len(w_reserved),
                'concurrency': w_stats.get('pool', {}).get('max-concurrency', 'N/A'),
                'pid': w_stats.get('pid', 'N/A'),
                'processed': w_total
            })

    return {
        'redis_status': redis_status,
        'redis_error': redis_error,
        'redis_latency': redis_latency,
        'queue_length': queue_length,
        'redis_url': settings.CELERY_BROKER_URL,
        'workers': worker_data,
        'worker_count': len(worker_data),
        'total_processed': total_processed,
    }