import redis
import time
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q 
from waitlist_project.celery import app as celery_app
from django.contrib.auth.models import Group

from pilot_data.models import EveCharacter, EsiHeaderCache

# --- LEGACY / FALLBACK DEFAULTS ---
ROLE_HIERARCHY_DEFAULT = [
    'Admin', 'Leadership', 'Officer', 'Certified Trainer', 'Training CT',
    'Fleet Commander', 'Training FC', 'Assault FC', 'Line Commander',
    'Resident', 'Pilot', 'Public'
]

# ALIAS FOR BACKWARD COMPATIBILITY
ROLE_HIERARCHY = ROLE_HIERARCHY_DEFAULT

ROLES_ADMIN = ['Admin']
ROLES_FC = ROLE_HIERARCHY_DEFAULT[:8]
ROLES_MANAGEMENT = ROLE_HIERARCHY_DEFAULT[:10]

# --- CAPABILITY REGISTRY ---
SYSTEM_CAPABILITIES = [
    {"category": "System Administration", "name": "Full System Access", "desc": "Manage SDE, Roles, System Health, Unlink Alts.", "roles": ROLES_ADMIN},
    {"category": "System Administration", "name": "Manage Doctrines", "desc": "Create, Edit, and Delete Doctrine Fits.", "roles": ROLES_ADMIN},
    {"category": "System Administration", "name": "Promote/Demote Users", "desc": "Assign roles to users (up to own rank) and Unlink Alts.", "roles": ROLES_ADMIN},
    {"category": "Fleet Operations", "name": "Fleet Command", "desc": "Create/Close Fleets, Take Command, FC Actions (Approve/Invite).", "roles": ROLES_FC},
    {"category": "Fleet Operations", "name": "Inspect Pilots", "desc": "View full pilot details (Skills, Assets) in User Search.", "roles": ROLES_FC},
    {"category": "Fleet Operations", "name": "View Fleet Overview", "desc": "See the live fleet composition sidebar on the dashboard.", "roles": ROLES_MANAGEMENT},
    {"category": "General", "name": "Management Access", "desc": "Access the Management Dashboard (limited view).", "roles": ROLES_MANAGEMENT},
    {"category": "General", "name": "Join Waitlists", "desc": "X-Up for fleets.", "roles": ROLE_HIERARCHY_DEFAULT}
]

# --- DYNAMIC HIERARCHY HELPERS ---

def get_role_hierarchy():
    """
    Fetches roles from DB ordered by Priority.
    Returns list of strings.
    """
    # Check if RolePriority table is populated
    # We do a cheap check or cache this in a real prod env
    from core.models import RolePriority
    
    if RolePriority.objects.exists():
        # Return names ordered by level
        return list(Group.objects.filter(priority_config__isnull=False).order_by('priority_config__level').values_list('name', flat=True))
    
    return ROLE_HIERARCHY_DEFAULT

def get_role_priority(group_name):
    """
    Returns integer priority. Lower is better.
    """
    # Try DB first
    from core.models import RolePriority
    try:
        priority = RolePriority.objects.get(group__name=group_name)
        return priority.level
    except (RolePriority.DoesNotExist, Group.DoesNotExist):
        pass

    # Fallback to list
    try:
        return ROLE_HIERARCHY_DEFAULT.index(group_name)
    except ValueError:
        return 999

def get_user_highest_role(user):
    if user.is_superuser: return 'Admin', 0
    
    user_groups = list(user.groups.values_list('name', flat=True))
    if not user_groups: return 'Public', 999
    
    # Get all priorities in one query if possible, or iterate
    best_role = 'Public'
    best_index = 999
    
    for group in user_groups:
        idx = get_role_priority(group)
        if idx < best_index:
            best_index = idx
            best_role = group
            
    return best_role, best_index

def can_manage_role(actor, target_role_name):
    if actor.is_superuser: return True
    _, actor_index = get_user_highest_role(actor)
    target_index = get_role_priority(target_role_name)
    # Strictly less: Can only manage roles BELOW you
    return actor_index < target_index

# --- SYSTEM STATUS UTILS ---

def get_system_status():
    """
    Fetches Redis connection status, Queue depth, Celery Worker inspection data,
    AND ESI Token Health statistics.
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
        q_len = r.llen('celery')
        queue_length = int(q_len) if q_len is not None else 0
        redis_status = "ONLINE"
    except Exception as e:
        redis_error = str(e)
        queue_length = 0

    # 2. Inspect Celery Workers
    inspector = celery_app.control.inspect(timeout=0.5)
    
    workers = {}
    active_tasks = {}
    reserved_tasks = {}
    stats = {}
    total_processed = 0

    try:
        workers_ping = inspector.ping()
        if workers_ping:
            workers = workers_ping
            active_tasks = inspector.active() or {}
            reserved_tasks = inspector.reserved() or {}
            stats = inspector.stats() or {}
    except Exception as e:
        if not redis_error:
            redis_error = f"Celery Inspect Error: {str(e)}"

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

    # 3. ESI TOKEN HEALTH & USER STATS
    total_characters = EveCharacter.objects.count()
    
    # Thresholds
    stale_threshold = timezone.now() - timedelta(minutes=60)
    active_30d_threshold = timezone.now() - timedelta(days=30)
    
    stale_count = EveCharacter.objects.filter(last_updated__lt=stale_threshold).count()
    users_online_count = EveCharacter.objects.filter(is_online=True).count()
    
    # NEW: Active in last 30 days (based on last_login_at or last_updated if login not tracked)
    # Using Q object to check either field
    active_30d_count = EveCharacter.objects.filter(
        Q(last_login_at__gte=active_30d_threshold) | 
        Q(last_updated__gte=active_30d_threshold)
    ).count()
    
    invalid_token_count = 0
    for char in EveCharacter.objects.all().iterator():
        if not char.refresh_token:
            invalid_token_count += 1
            
    if total_characters > 0:
        esi_health_percent = int(((total_characters - stale_count) / total_characters * 100))
    else:
        esi_health_percent = 0

    # 4. OUTSTANDING ENDPOINT CALLS (SPLIT LOGIC)
    now = timezone.now()
    grace_period = now - timedelta(minutes=15)

    # --- A. READY TO QUEUE (Active Queue) ---
    raw_queued = EsiHeaderCache.objects.filter(
        expires__lte=now
    ).filter(
        Q(endpoint_name='online') | 
        Q(character__is_online=True) | 
        Q(expires__lte=grace_period)
    ).values('endpoint_name').annotate(
        pending_count=Count('id')
    ).order_by('-pending_count')
    
    queued_breakdown = list(raw_queued)

    # Part 2: Safety Net (Full Refresh Candidates)
    safety_net_threshold = now - timedelta(hours=24)
    safety_net_count = EveCharacter.objects.filter(
        Q(last_updated__isnull=True) | Q(last_updated__lt=safety_net_threshold)
    ).count()

    if safety_net_count > 0:
        queued_breakdown.append({
            'endpoint_name': 'Safety Net (Full)',
            'pending_count': safety_net_count
        })

    # --- B. DELAYED (Throttled) ---
    delayed_breakdown = EsiHeaderCache.objects.filter(
        expires__lte=now
    ).exclude(
        Q(endpoint_name='online') | 
        Q(character__is_online=True) | 
        Q(expires__lte=grace_period)
    ).values('endpoint_name').annotate(
        pending_count=Count('id')
    ).order_by('-pending_count')

    return {
        'redis_status': redis_status,
        'redis_error': redis_error,
        'redis_latency': redis_latency,
        'queue_length': queue_length,
        'redis_url': settings.CELERY_BROKER_URL,
        'workers': worker_data,
        'worker_count': len(worker_data),
        'total_processed': total_processed,
        'total_characters': total_characters,
        'stale_count': stale_count,
        'invalid_token_count': invalid_token_count,
        'users_online_count': users_online_count,
        'active_30d_count': active_30d_count, # NEW
        'esi_health_percent': esi_health_percent,
        'queued_breakdown': queued_breakdown,     
        'delayed_breakdown': delayed_breakdown,   
    }