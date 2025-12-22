import redis
import time
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q, Subquery
from waitlist_project.celery import app as celery_app
from django.contrib.auth.models import Group, User
from django.core.cache import cache

from pilot_data.models import EveCharacter, EsiHeaderCache, ItemType, ItemGroup, SkillHistory, SRPConfiguration
from esi.models import Token

# --- LEGACY / FALLBACK DEFAULTS ---
ROLE_HIERARCHY_DEFAULT = [
    'Admin', 
    'Leadership', 
    'Officer', 
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

# Define FCs explicitly
ROLES_FC = [
    'Admin', 'Leadership', 'Officer',
    'Fleet Commander', 'Training FC', 'Assault FC'
]

# Management covers up to Resident (Staff)
ROLES_MANAGEMENT = ROLE_HIERARCHY_DEFAULT[:10] 

# --- CAPABILITY REGISTRY (REVAMPED) ---
# Explicit slugs ensure database matches code decorators exactly.
SYSTEM_CAPABILITIES = [
    # --- SYSTEM ---
    {
        "slug": "access_admin", 
        "category": "System", 
        "name": "Full System Access", 
        "desc": "Manage SDE, Roles, System Health, Unlink Alts.", 
        "roles": ROLES_ADMIN
    },
    {
        "slug": "manage_analysis_rules", 
        "category": "System", 
        "name": "Manage Analysis Rules", 
        "desc": "Configure item comparison logic (Higher/Lower is Better).", 
        "roles": ROLES_ADMIN
    },
    {
        "slug": "view_sensitive_data", 
        "category": "System", 
        "name": "View Sensitive Data", 
        "desc": "View unobfuscated financial data in pilot profiles.", 
        "roles": ROLES_ADMIN
    },

    # --- MANAGEMENT ---
    {
        "slug": "access_management", 
        "category": "Management", 
        "name": "Management Access", 
        "desc": "Access the Management Dashboard.", 
        "roles": ROLES_MANAGEMENT
    },
    {
        "slug": "manage_bans", 
        "category": "Management", 
        "name": "Manage Bans", 
        "desc": "Ban and unban users.", 
        "roles": ['Admin', 'Leadership', 'Officer'] # Restricted to Officers+ typically
    },
    {
        "slug": "view_ban_audit_log", 
        "category": "Management", 
        "name": "View Ban Audit Log", 
        "desc": "View the audit log of ban actions.", 
        "roles": ['Admin', 'Leadership']
    },

    # --- SRP ---
    {
        "slug": "manage_srp_source", 
        "category": "SRP & Finance", 
        "name": "Manage SRP Source", 
        "desc": "Configure the SRP data source character.", 
        "roles": ['Admin', 'Leadership']
    },
    {
        "slug": "view_srp_dashboard", 
        "category": "SRP & Finance", 
        "name": "View SRP Dashboard", 
        "desc": "Access SRP Wallet History and Analytics.", 
        "roles": ['Admin', 'Leadership', 'Officer']
    },

    # --- FLEET OPERATIONS ---
    {
        "slug": "access_fleet_command", 
        "category": "Fleet Ops", 
        "name": "Fleet Command", 
        "desc": "Create/Close Fleets, Take Command, FC Actions.", 
        "roles": ROLES_FC
    },
    {
        "slug": "inspect_pilots", 
        "category": "Fleet Ops", 
        "name": "Inspect Pilots", 
        "desc": "View full pilot details in Search.", 
        "roles": ROLES_FC
    },
    {
        "slug": "view_fleet_overview", 
        "category": "Fleet Ops", 
        "name": "View Fleet Overview", 
        "desc": "See live fleet composition on dashboard.", 
        "roles": ROLES_MANAGEMENT
    },
    
    # --- GENERAL ---
    {
        "slug": "join_waitlists", 
        "category": "General", 
        "name": "Join Waitlists", 
        "desc": "Ability to X-Up for fleets.", 
        "roles": ROLE_HIERARCHY_DEFAULT
    },
    
    # --- RE-ADDED MISSING CAPABILITIES FROM MIGRATION ---
    {
        "slug": "manage_doctrines",
        "category": "System",
        "name": "Manage Doctrines",
        "desc": "Create, Edit, and Delete Doctrine Fits.",
        "roles": ROLES_ADMIN
    },
    {
        "slug": "promote_demote_users",
        "category": "Management",
        "name": "Promote/Demote Users",
        "desc": "Assign roles to users (up to own rank).",
        "roles": ROLES_ADMIN
    },
    {
        "slug": "manage_skill_requirements",
        "category": "System",
        "name": "Manage Skill Requirements",
        "desc": "Configure mandatory skills for hulls or specific fits.",
        "roles": ROLES_ADMIN
    }
]

# --- BACKGROUND TASK CONFIG ---
# Only these endpoints are processed by the background scheduler.
BACKGROUND_ENDPOINTS = [
    'skills', 'queue', 'ship', 'wallet', 
    'lp', 'implants', 'public_info', 'history'
]

# --- DYNAMIC HIERARCHY HELPERS ---

def get_role_hierarchy():
    """
    Fetches roles from DB ordered by Priority.
    Returns list of strings.
    """
    from core.models import RolePriority
    
    if RolePriority.objects.exists():
        return list(Group.objects.filter(priority_config__isnull=False).order_by('priority_config__level').values_list('name', flat=True))
    
    return ROLE_HIERARCHY_DEFAULT

def get_role_priority(group_name):
    """
    Returns integer priority. Lower is better.
    """
    from core.models import RolePriority
    try:
        priority = RolePriority.objects.get(group__name=group_name)
        return priority.level
    except (RolePriority.DoesNotExist, Group.DoesNotExist):
        pass

    try:
        return ROLE_HIERARCHY_DEFAULT.index(group_name)
    except ValueError:
        return 999

def get_user_highest_role(user):
    if user.is_superuser: return True, 0
    
    user_groups = list(user.groups.values_list('name', flat=True))
    if not user_groups: return 'Public', 999
    
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
    # We use a lightweight inspect (stats/ping only) to list active workers.
    # Active task monitoring is handled via WebSocket events (celery_signals.py).
    inspector = celery_app.control.inspect(timeout=2.0)
    
    worker_stats = {}
    worker_ping = {}
    
    try:
        worker_ping = inspector.ping() or {}
        if worker_ping:
            worker_stats = inspector.stats() or {}
    except Exception as e:
        if not redis_error:
            redis_error = f"Celery Inspect Error: {str(e)}"

    worker_data = []
    
    # Process Worker Data
    for worker_name, response in worker_ping.items():
        w_stats = worker_stats.get(worker_name, {})
        w_total = sum(w_stats.get('total', {}).values())
        
        worker_data.append({
            'name': worker_name,
            'status': 'Active' if response == 'pong' else 'Unknown',
            'active_count': 'N/A', # Not polling active tasks
            'reserved_count': 'N/A',
            'concurrency': w_stats.get('pool', {}).get('max-concurrency', 'N/A'),
            'pid': w_stats.get('pid', 'N/A'),
            'processed': w_total
        })

    # Cache total processed count
    total_processed = 0
    if worker_data:
        current_total = sum(w['processed'] for w in worker_data if isinstance(w['processed'], int))
        total_processed = current_total
        cache.set('monitor_total_processed_stable', total_processed, timeout=3600)
    else:
        total_processed = cache.get('monitor_total_processed_stable') or 0

    total_characters = EveCharacter.objects.count()
    stale_threshold = timezone.now() - timedelta(hours=24)
    active_30d_threshold = timezone.now() - timedelta(days=30)
    
    stale_count = EveCharacter.objects.filter(last_updated__lt=stale_threshold).count()
    
    # New Token Metrics
    total_tokens = Token.objects.count()
    
    # Missing Tokens: Characters that exist but have no corresponding ESI token
    missing_token_count = EveCharacter.objects.exclude(
        character_id__in=Subquery(Token.objects.values('character_id'))
    ).count()
    
    # Expired Tokens: Tokens that are past their expiry date (need refresh)
    expired_token_count = Token.objects.all().get_expired().count()
            
    if total_characters > 0:
        esi_health_percent = int(((total_characters - stale_count) / total_characters * 100))
    else:
        esi_health_percent = 0

    # --- OPERATIONAL METRICS ---
    from waitlist_data.models import Fleet, WaitlistEntry, FleetActivity

    # 1. Active in Fleets (Waitlist Actions)
    active_waitlist_30d = FleetActivity.objects.filter(
        timestamp__gte=timezone.now() - timedelta(days=30)
    ).values('character_id').distinct().count()

    # 2. Active on Site (Logins)
    active_site_30d = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()

    active_fleets_count = Fleet.objects.filter(is_active=True).count()
    
    # Pilots specifically waiting for an active fleet
    pending_pilots_count = WaitlistEntry.objects.filter(
        status='pending', 
        fleet__is_active=True
    ).count()

    # Pilots currently flying in an active fleet
    active_pilots_count = WaitlistEntry.objects.filter(
        status__in=['approved', 'invited'],
        fleet__is_active=True
    ).count()

    # --- SRP METRICS ---
    srp_config = SRPConfiguration.objects.first()
    last_srp_sync = srp_config.last_sync if (srp_config and srp_config.last_sync) else None

    now = timezone.now()
    
    raw_queued = EsiHeaderCache.objects.filter(
        endpoint_name__in=BACKGROUND_ENDPOINTS, 
        expires__lte=now
    ).values('endpoint_name').annotate(
        pending_count=Count('id')
    ).order_by('-pending_count')
    
    queued_breakdown = list(raw_queued)

    safety_net_threshold = now - timedelta(hours=24)
    safety_net_count = EveCharacter.objects.filter(
        Q(last_updated__isnull=True) | Q(last_updated__lt=safety_net_threshold)
    ).count()

    if safety_net_count > 0:
        queued_breakdown.append({
            'endpoint_name': 'Safety Net (Full)',
            'pending_count': safety_net_count
        })

    delayed_breakdown = []

    from esi_calls.token_manager import check_esi_status
    esi_status_bool = check_esi_status()

    system_load_percent = min(int(queue_length), 100) 
    
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
        'missing_token_count': missing_token_count,
        'expired_token_count': expired_token_count,
        'total_tokens': total_tokens,
        'active_waitlist_30d': active_waitlist_30d,
        'active_site_30d': active_site_30d, 
        'esi_health_percent': esi_health_percent,
        'queued_breakdown': queued_breakdown,     
        'delayed_breakdown': delayed_breakdown,   
        'esi_server_status': esi_status_bool,
        'system_load_percent': system_load_percent,
        'load_hue': load_hue,
        # New Metrics
        'active_fleets_count': active_fleets_count,
        'pending_pilots_count': pending_pilots_count,
        'active_pilots_count': active_pilots_count,
        'last_srp_sync': last_srp_sync
    }

def get_character_data(active_char):
    esi_data = {'implants': [], 'queue': [], 'history': [], 'skill_history': []}
    grouped_skills = {}
    if not active_char: return esi_data, grouped_skills

    granted = set(active_char.granted_scopes.split()) if active_char.granted_scopes else set()
    # Backwards compatibility: If empty, assume all Base are present? 
    # Or just check emptiness. If empty and token exists, it might be old legacy.
    # But for now, we trust the set.

    # 1. IMPLANTS (Scope: esi-clones.read_implants.v1 - BASE)
    # Base scopes should always be there, but good to check.
    if 'esi-clones.read_implants.v1' in granted or not active_char.granted_scopes:
        implants = active_char.implants.all()
        if implants.exists():
            imp_ids = [i.type_id for i in implants]
            known_items = ItemType.objects.filter(type_id__in=imp_ids).in_bulk(field_name='type_id')
            for imp in implants:
                item = known_items.get(imp.type_id)
                esi_data['implants'].append({
                    'id': imp.type_id,
                    'name': item.type_name if item else f"Unknown ({imp.type_id})",
                    'icon_url': f"https://images.evetech.net/types/{imp.type_id}/icon?size=32"
                })

    # 2. SKILL QUEUE (Scope: esi-skills.read_skillqueue.v1 - BASE)
    if 'esi-skills.read_skillqueue.v1' in granted or not active_char.granted_scopes:
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
    
    # 3. CORP HISTORY (Public Data - Always Available if we have the char)
    history_entries = active_char.corp_history.all().order_by('-start_date')
    esi_data['history'] = [
        {
            'corporation_id': h.corporation_id,
            'corporation_name': h.corporation_name,
            'start_date': h.start_date
        } for h in history_entries
    ]

    # 4. SKILL HISTORY (Derived from Skills + Internal Logging - Effectively Base/Public)
    try:
        raw_history = active_char.skill_history.all().order_by('-logged_at')[:30]
        if raw_history.exists():
            h_ids = [h.skill_id for h in raw_history]
            h_items = ItemType.objects.filter(type_id__in=h_ids).in_bulk(field_name='type_id')
            for h in raw_history:
                item = h_items.get(h.skill_id)
                esi_data['skill_history'].append({
                    'name': item.type_name if item else f"Unknown Skill {h.skill_id}",
                    'old_level': h.old_level, 'new_level': h.new_level,
                    'sp_diff': h.new_sp - h.old_sp, 'logged_at': h.logged_at
                })
    except Exception: pass

    # 5. SKILLS (Scope: esi-skills.read_skills.v1 - BASE)
    if 'esi-skills.read_skills.v1' in granted or not active_char.granted_scopes:
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

    # 6. SHIP TYPE (Scope: esi-location.read_ship_type.v1 - OPTIONAL)
    # We resolve the name if we have the ID, but the ID comes from ESI.
    # If we don't have the scope, the background task won't update the ID, so it might be stale or None.
    # We just resolve whatever ID is in the DB.
    if active_char.current_ship_type_id:
            try:
                ship_item = ItemType.objects.get(type_id=active_char.current_ship_type_id)
                active_char.ship_type_name = ship_item.type_name
            except ItemType.DoesNotExist:
                active_char.ship_type_name = "Unknown Hull"
    
    return esi_data, grouped_skills