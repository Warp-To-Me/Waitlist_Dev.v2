import redis
import time
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q 
from waitlist_project.celery import app as celery_app
from django.contrib.auth.models import Group
from django.core.cache import cache

from pilot_data.models import EveCharacter, EsiHeaderCache, ItemType, ItemGroup, SkillHistory

# --- LEGACY / FALLBACK DEFAULTS ---
ROLE_HIERARCHY_DEFAULT = [
    'Admin', 
    'Leadership', 
    'Officer', 
    'Certified Trainer', 
    'Training CT',
    'Fleet Commander', 
    'Training FC', 
    'Assault FC', 
    'Line Commander',
    'Resident',
    'Public'
]

# ALIAS FOR BACKWARD COMPATIBILITY
ROLE_HIERARCHY = ROLE_HIERARCHY_DEFAULT

ROLES_ADMIN = ['Admin']

# Define FCs explicitly to avoid accidental inclusion of new roles like Personnel Manager
ROLES_FC = [
    'Admin', 'Leadership', 'Officer', 'Certified Trainer', 'Training CT',
    'Fleet Commander', 'Training FC', 'Assault FC'
]

ROLES_MANAGEMENT = ROLE_HIERARCHY_DEFAULT[:10] # Covers up to Resident

# --- CAPABILITY REGISTRY ---
SYSTEM_CAPABILITIES = [
    {"category": "System Administration", "name": "Full System Access", "desc": "Manage SDE, Roles, System Health, Unlink Alts.", "roles": ROLES_ADMIN},
    {"category": "System Administration", "name": "Manage Doctrines", "desc": "Create, Edit, and Delete Doctrine Fits.", "roles": ROLES_ADMIN},
    {"category": "System Administration", "name": "Promote/Demote Users", "desc": "Assign roles to users (up to own rank) and Unlink Alts.", "roles": ROLES_ADMIN},
    {"category": "System Administration", "name": "Manage Analysis Rules", "desc": "Configure item comparison logic (Higher/Lower is Better).", "roles": ROLES_ADMIN},
    {"category": "System Administration", "name": "View Sensitive Data", "desc": "View unobfuscated financial data in pilot profiles.", "roles": ['Admin']},
    
    # --- NEW SRP CAPABILITIES ---
    {"category": "SRP & Finance", "name": "Manage SRP Source", "desc": "Configure the SRP data source character and settings.", "roles": ['Admin', 'Leadership']},
    {"category": "SRP & Finance", "name": "View SRP Dashboard", "desc": "Access the SRP Wallet History and Analytics page.", "roles": ['Admin', 'Leadership', 'Officer']},

    {"category": "Fleet Operations", "name": "Fleet Command", "desc": "Create/Close Fleets, Take Command, FC Actions (Approve/Invite).", "roles": ROLES_FC},
    {"category": "Fleet Operations", "name": "Inspect Pilots", "desc": "View full pilot details (Skills, Assets) in User Search.", "roles": ROLES_FC},
    {"category": "Fleet Operations", "name": "View Fleet Overview", "desc": "See the live fleet composition sidebar on the dashboard.", "roles": ROLES_MANAGEMENT},
    {"category": "General", "name": "Management Access", "desc": "Access the Management Dashboard (limited view).", "roles": ROLES_MANAGEMENT},
    {"category": "General", "name": "Join Waitlists", "desc": "X-Up for fleets.", "roles": ROLE_HIERARCHY_DEFAULT}
]

# --- BACKGROUND TASK CONFIG ---
# Only these endpoints are processed by the background scheduler.
# We filter the status page to match this list so we don't show "Fleet" calls as queued.
BACKGROUND_ENDPOINTS = [
    'online', 'skills', 'queue', 'ship', 'wallet', 
    'lp', 'implants', 'public_info', 'history'
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
    if user.is_superuser: return True, 0
    
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
    # FIX: Increased timeout from 0.5 to 1.0 to reduce "jumping" stats
    inspector = celery_app.control.inspect(timeout=1.0)
    
    workers = {}
    active_tasks = {}
    reserved_tasks = {}
    stats = {}
    
    # Calculated below
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

    # --- ENRICHMENT STEP: Resolve Character Names for Active Tasks ---
    char_name_map = {}
    
    if active_tasks:
        all_char_ids = set()
        for worker_tasks in active_tasks.values():
            for task in worker_tasks:
                # Look for refresh_character_task or similar variants
                if 'refresh_character' in task.get('name', ''):
                    args = task.get('args', [])
                    if args and len(args) > 0:
                        try:
                            # 1. Get Char ID
                            char_id = int(args[0])
                            all_char_ids.add(char_id)
                            task['enriched_char_id'] = char_id
                            
                            # 2. Format Info (Endpoints)
                            endpoints = args[1] if len(args) > 1 else None
                            force = args[2] if len(args) > 2 else False
                            
                            info_str = ""
                            if force: info_str += "[FORCED] "
                            
                            if endpoints is None:
                                info_str += "Full Update"
                            else:
                                # Clean up list string: ['skills', 'wallet'] -> skills, wallet
                                ep_str = str(endpoints).replace("'", "").replace("[", "").replace("]", "")
                                info_str += f"Partial: {ep_str}"
                                
                            task['enriched_info'] = info_str
                        except (ValueError, TypeError, IndexError):
                            pass
        
        # Bulk Fetch Names
        if all_char_ids:
            found = EveCharacter.objects.filter(character_id__in=list(all_char_ids)).values('character_id', 'character_name')
            for f in found:
                char_name_map[f['character_id']] = f['character_name']

    # --- WORKER DATA CONSTRUCTION ---
    worker_data = []
    current_raw_processed = 0

    if workers:
        for worker_name, response in workers.items():
            w_active = active_tasks.get(worker_name, [])
            w_reserved = reserved_tasks.get(worker_name, [])
            w_stats = stats.get(worker_name, {})
            w_total = sum(w_stats.get('total', {}).values())
            
            # Apply names to tasks
            for task in w_active:
                if 'enriched_char_id' in task:
                    task['enriched_name'] = char_name_map.get(task['enriched_char_id'], 'Unknown Pilot')
            
            current_raw_processed += w_total
            
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

    # --- STABILIZATION FIX ---
    # Use Cache to persist the 'Total Processed' count if inspection fails/timeouts.
    # This prevents the UI card from flashing "0" during minor blips.
    cache_key_proc = 'monitor_total_processed_stable'
    cached_total = cache.get(cache_key_proc) or 0
    
    if workers:
        # We have live data
        total_processed = current_raw_processed
        # Only update cache if we have a valid number
        if total_processed > 0:
            cache.set(cache_key_proc, total_processed, timeout=3600)
    else:
        # Inspection failed or returned empty - fallback to cache to hide the glitch
        total_processed = cached_total

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
        endpoint_name__in=BACKGROUND_ENDPOINTS, # FILTER: Only show what workers actually process
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
        endpoint_name__in=BACKGROUND_ENDPOINTS, # FILTER: Only show what workers actually process
        expires__lte=now
    ).exclude(
        Q(endpoint_name='online') | 
        Q(character__is_online=True) | 
        Q(expires__lte=grace_period)
    ).values('endpoint_name').annotate(
        pending_count=Count('id')
    ).order_by('-pending_count')

    # NEW: Fetch ESI Status
    from esi_calls.token_manager import check_esi_status
    esi_status_bool = check_esi_status()

    # --- NEW: VISUAL LOAD CALCULATION ---
    # Treats 100 tasks as 100% capacity for visual scaling
    system_load_percent = min(int(queue_length), 100) 
    
    # Calculate HSL Hue: 120 (Green) -> 0 (Red)
    # Formula: 120 - (percent * 1.2)
    load_hue = int(120 - (system_load_percent * 1.2))
    if load_hue < 0: load_hue = 0

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
        'active_30d_count': active_30d_count, 
        'esi_health_percent': esi_health_percent,
        'queued_breakdown': queued_breakdown,     
        'delayed_breakdown': delayed_breakdown,   
        'esi_server_status': esi_status_bool,
        'system_load_percent': system_load_percent, # PASSED TO TEMPLATE
        'load_hue': load_hue # PASSED TO TEMPLATE
    }

# --- DATA BUILDER HELPER (Moved from views.py) ---
def get_character_data(active_char):
    esi_data = {'implants': [], 'queue': [], 'history': [], 'skill_history': []}
    grouped_skills = {}
    if not active_char: return esi_data, grouped_skills
    implants = active_char.implants.all()
    if implants.exists():
        imp_ids = [i.type_id for i in implants]
        known_items = ItemType.objects.filter(type_id__in=imp_ids).in_bulk(field_name='type_id')
        for imp in implants:
            item = known_items.get(imp.type_id)
            esi_data['implants'].append({
                'id': imp.type_id,
                'name': item.type_name if item else f"Unknown ({imp.type_id})",
                'icon_url': f"https://images.evetech.net/types/{{imp.type_id}}/icon?size=32"
            })
    queue = active_char.skill_queue.all().order_by('queue_position')
    q_ids = [q.skill_id for q in queue]
    q_types = ItemType.objects.filter(type_id__in=q_ids).in_bulk(field_name='type_id')
    for q in queue:
            item = q_types.get(q.skill_id)
            esi_data['queue'].append({
                'skill_id': q.skill_id,
                'name': item.type_name if item else str(q.skill_id),
                'finished_level': q.finished_level,
                'finish_date': q.finish_date
            })
    esi_data['history'] = active_char.corp_history.all().order_by('-start_date')
    try:
        raw_history = active_char.skill_history.all().order_by('-logged_at')[:30]
        if raw_history.exists():
            h_ids = [h.skill_id for h in raw_history]
            h_items = ItemType.objects.filter(type_id__in=h_ids).in_bulk(field_name='type_id')
            for h in raw_history:
                item = h_items.get(h.skill_id)
                esi_data['skill_history'].append({
                    'name': item.type_name if item else f"Unknown Skill {{h.skill_id}}",
                    'old_level': h.old_level, 'new_level': h.new_level,
                    'sp_diff': h.new_sp - h.old_sp, 'logged_at': h.logged_at
                })
    except Exception: pass
    skills = active_char.skills.select_related().all()
    if skills.exists():
        s_ids = [s.skill_id for s in skills]
        s_types = ItemType.objects.filter(type_id__in=s_ids).in_bulk(field_name='type_id')
        group_ids = set(st.group_id for st in s_types.values())
        skill_groups = ItemGroup.objects.filter(group_id__in=group_ids).in_bulk(field_name='group_id')
        for s in skills:
            item = s_types.get(s.skill_id)
            if item:
                group = skill_groups.get(item.group_id)
                group_name = group.group_name if group else "Unknown"
                if group_name not in grouped_skills: grouped_skills[group_name] = []
                grouped_skills[group_name].append({
                    'name': item.type_name, 'level': s.active_skill_level, 'sp': s.skillpoints_in_skill
                })
        for g in grouped_skills: grouped_skills[g].sort(key=lambda x: x['name'])
        grouped_skills = dict(sorted(grouped_skills.items()))
    if active_char.current_ship_type_id:
            try:
                ship_item = ItemType.objects.get(type_id=active_char.current_ship_type_id)
                active_char.ship_type_name = ship_item.type_name
            except ItemType.DoesNotExist:
                active_char.ship_type_name = "Unknown Hull"
    return esi_data, grouped_skills