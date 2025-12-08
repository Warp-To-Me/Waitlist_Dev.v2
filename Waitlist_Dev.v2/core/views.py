from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum, Subquery, OuterRef
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.views.decorators.http import require_POST
import json

# Import Utils
from core.utils import (
    get_system_status, get_user_highest_role, can_manage_role, get_role_hierarchy,
    ROLE_HIERARCHY, ROLES_ADMIN, ROLES_FC, ROLES_MANAGEMENT, SYSTEM_CAPABILITIES
)

# Import Celery App
from waitlist_project.celery import app as celery_app

# Import Models
from pilot_data.models import (
    EveCharacter, ItemType, ItemGroup, SkillHistory, TypeAttribute, 
    AttributeDefinition, FitAnalysisRule
)
from waitlist_data.models import Fleet
from esi_calls.token_manager import update_character_data
from waitlist_data.models import DoctrineCategory, DoctrineFit, FitModule, DoctrineTag
from core.eft_parser import EFTParser
from core.models import Capability, RolePriority

# --- Helper for SPA Rendering ---
def get_template_base(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return 'base_content.html'
    return 'base.html'

# --- Permission Helpers (Enhanced) ---

def get_user_capabilities(user):
    """
    Returns a set of capability slugs for the user.
    """
    if user.is_superuser:
        return set(Capability.objects.values_list('slug', flat=True))
    
    return set(Capability.objects.filter(groups__user=user).values_list('slug', flat=True).distinct())

def is_management(user):
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='access_management').exists(): return True
    return user.groups.filter(name__in=ROLES_MANAGEMENT).exists()

def is_fleet_command(user):
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='access_fleet_command').exists(): return True
    return user.groups.filter(name__in=ROLES_FC).exists()

def is_admin(user):
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='access_admin').exists(): return True
    return user.groups.filter(name__in=ROLES_ADMIN).exists()

def can_manage_doctrines(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='manage_doctrines').exists()

def can_manage_roles(user):
    """
    Checks if user has permission to promote/demote others.
    """
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='promote_demote_users').exists(): return True
    return user.groups.filter(name__in=ROLES_ADMIN).exists()

def get_mgmt_context(user):
    """
    Injects the granular permission set into the template.
    """
    perms = get_user_capabilities(user)
    return {
        'user_perms': perms,
        'can_view_fleets': 'access_fleet_command' in perms,
        'can_view_admin': 'access_admin' in perms
    }

# --- Data Builder Helper ---
def _get_character_data(active_char):
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
                'icon_url': f"https://images.evetech.net/types/{imp.type_id}/icon?size=32"
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
                    'name': item.type_name if item else f"Unknown Skill {h.skill_id}",
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

# --- Public Views ---

def landing_page(request):
    active_fleets_qs = Fleet.objects.filter(is_active=True).select_related('commander').order_by('-created_at')
    if request.user.is_authenticated and active_fleets_qs.count() == 1:
        return redirect('fleet_dashboard', token=active_fleets_qs.first().join_token)
    fleets_list = list(active_fleets_qs)
    if fleets_list:
        commander_user_ids = [f.commander_id for f in fleets_list]
        mains = EveCharacter.objects.filter(user_id__in=commander_user_ids, is_main=True).values('user_id', 'character_name')
        fc_name_map = {m['user_id']: m['character_name'] for m in mains}
        missing_ids = set(commander_user_ids) - set(fc_name_map.keys())
        if missing_ids:
            others = EveCharacter.objects.filter(user_id__in=missing_ids).values('user_id', 'character_name')
            for o in others:
                if o['user_id'] not in fc_name_map: fc_name_map[o['user_id']] = o['character_name']
        for fleet in fleets_list:
            fleet.fc_name = fc_name_map.get(fleet.commander_id, fleet.commander.username)
    context = { 'active_fleets': fleets_list, 'base_template': get_template_base(request) }
    return render(request, 'landing.html', context)

# --- Profile & Alt Management ---

@login_required
def profile_view(request):
    characters = request.user.characters.all()
    active_char_id = request.session.get('active_char_id')
    if active_char_id: active_char = characters.filter(character_id=active_char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char and characters.exists(): active_char = characters.first()
    esi_data, grouped_skills = _get_character_data(active_char)
    token_missing = False
    if active_char and not active_char.refresh_token: token_missing = True
    totals = characters.aggregate(wallet_sum=Sum('wallet_balance'), lp_sum=Sum('concord_lp'), sp_sum=Sum('total_sp'))
    context = {
        'active_char': active_char, 'characters': characters,
        'esi': esi_data, 'grouped_skills': grouped_skills, 'token_missing': token_missing,
        'total_wallet': totals['wallet_sum'] or 0, 'total_lp': totals['lp_sum'] or 0,
        'account_total_sp': totals['sp_sum'] or 0, 'is_admin_user': is_admin(request.user),
        'base_template': get_template_base(request) 
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/profile_content.html', context)
    return render(request, 'profile.html', context)

@login_required
def api_refresh_profile(request, char_id):
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    if not character.refresh_token: return JsonResponse({'success': False, 'error': 'No refresh token'})
    success = update_character_data(character)
    return JsonResponse({'success': success, 'last_updated': timezone.now().isoformat()})

@login_required
def switch_character(request, char_id):
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    request.session['active_char_id'] = character.character_id
    return redirect('profile')

@login_required
def make_main(request, char_id):
    new_main = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    request.user.characters.update(is_main=False)
    new_main.is_main = True
    new_main.save()
    request.session['active_char_id'] = new_main.character_id
    return redirect('profile')

def access_denied(request):
    context = { 'base_template': get_template_base(request) }
    return render(request, 'access_denied.html', context)

# --- MANAGEMENT VIEWS ---

@login_required
@user_passes_test(is_management)
def management_dashboard(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    user_growth = User.objects.filter(date_joined__gte=thirty_days_ago).annotate(date=TruncDate('date_joined')).values('date').annotate(count=Count('id')).order_by('date')
    growth_labels = [entry['date'].strftime('%b %d') for entry in user_growth]
    growth_data = [entry['count'] for entry in user_growth]
    corp_distribution = EveCharacter.objects.values('corporation_name').annotate(count=Count('id')).order_by('-count')[:5]
    context = {
        'total_users': User.objects.count(), 'total_fleets': Fleet.objects.count(),
        'active_fleets_count': Fleet.objects.filter(is_active=True).count(), 'total_characters': EveCharacter.objects.count(),
        'growth_labels': growth_labels, 'growth_data': growth_data,
        'corp_labels': [e['corporation_name'] for e in corp_distribution],
        'corp_data': [e['count'] for e in corp_distribution],
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/dashboard.html', context)

@login_required
@user_passes_test(is_fleet_command)
def management_users(request):
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'character')
    direction = request.GET.get('dir', 'asc')
    main_name_sq = EveCharacter.objects.filter(user=OuterRef('user'), is_main=True).values('character_name')[:1]
    char_qs = EveCharacter.objects.select_related('user').annotate(
        linked_count=Count('user__characters', distinct=True), main_char_name=Subquery(main_name_sq)
    )
    if query: char_qs = char_qs.filter(character_name__icontains=query)
    valid_sorts = {
        'character': 'character_name', 'main': 'main_char_name', 'linked': 'linked_count',
        'corporation': 'corporation_name', 'alliance': 'alliance_name', 'status': 'last_updated'
    }
    db_sort_field = valid_sorts.get(sort_by, 'character_name')
    if direction == 'desc': db_sort_field = '-' + db_sort_field
    char_qs = char_qs.order_by(db_sort_field)
    paginator = Paginator(char_qs, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'page_obj': page_obj, 'query': query, 'current_sort': sort_by, 'current_dir': direction,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/users.html', context)

@login_required
@user_passes_test(is_fleet_command)
def management_user_inspect(request, user_id, char_id=None):
    target_user = get_object_or_404(User, pk=user_id)
    characters = target_user.characters.all()
    if char_id: active_char = characters.filter(character_id=char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char: active_char = characters.filter(is_main=True).first()
    esi_data, grouped_skills = _get_character_data(active_char)
    totals = characters.aggregate(wallet_sum=Sum('wallet_balance'), lp_sum=Sum('concord_lp'), sp_sum=Sum('total_sp'))
    obfuscate_financials = not is_admin(request.user)
    context = {
        'active_char': active_char, 'characters': characters, 'esi': esi_data,
        'grouped_skills': grouped_skills, 'token_missing': False,
        'total_wallet': totals['wallet_sum'] or 0, 'total_lp': totals['lp_sum'] or 0,
        'account_total_sp': totals['sp_sum'] or 0, 'is_inspection_mode': True,
        'inspect_user_id': target_user.id, 'obfuscate_financials': obfuscate_financials,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/profile_content.html', context)
    return render(request, 'profile.html', context)

@login_required
@user_passes_test(is_admin)
@require_POST
def api_unlink_alt(request):
    try:
        data = json.loads(request.body)
        char_id = data.get('character_id')
    except json.JSONDecodeError: return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    if not char_id: return JsonResponse({'success': False, 'error': 'Character ID required'})
    char = get_object_or_404(EveCharacter, character_id=char_id)
    if not is_admin(request.user): return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    if char.is_main: return JsonResponse({'success': False, 'error': 'Cannot unlink a Main Character.'})
    char.delete()
    return JsonResponse({'success': True})

@login_required
@require_POST
def api_promote_alt(request):
    try:
        data = json.loads(request.body)
        char_id = data.get('character_id')
    except json.JSONDecodeError: return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    if not char_id: return JsonResponse({'success': False, 'error': 'Character ID required'})
    target_char = get_object_or_404(EveCharacter, character_id=char_id)
    target_user = target_char.user
    is_owner = (target_user == request.user)
    is_admin_user = is_admin(request.user)
    if not is_owner and not is_admin_user: return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    if target_char.is_main: return JsonResponse({'success': False, 'error': 'Character is already main.'})
    target_user.characters.update(is_main=False)
    target_char.is_main = True
    target_char.save()
    if is_owner: request.session['active_char_id'] = target_char.character_id
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_fleet_command)
def management_fleets(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            name = request.POST.get('name')
            if name: Fleet.objects.create(name=name, commander=request.user, is_active=True)
        elif action == 'close':
            fleet_id = request.POST.get('fleet_id')
            fleet = get_object_or_404(Fleet, id=fleet_id)
            fleet.is_active = False
            fleet.save()
        elif action == 'delete':
            fleet_id = request.POST.get('fleet_id')
            if is_admin(request.user): Fleet.objects.filter(id=fleet_id).delete()
        return redirect('management_fleets')
    fleets = Fleet.objects.all().order_by('-is_active', '-created_at')[:50]
    context = { 'fleets': fleets, 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/fleets.html', context)

@login_required
@user_passes_test(is_admin)
def management_sde(request):
    item_count = ItemType.objects.count()
    group_count = ItemGroup.objects.count()
    attr_count = TypeAttribute.objects.count()
    EXCLUDED_CATEGORIES = [2, 9, 11, 17, 20, 25, 30, 40, 46, 63, 91, 2118, 350001]
    excluded_group_ids = ItemGroup.objects.filter(category_id__in=EXCLUDED_CATEGORIES).values_list('group_id', flat=True)
    top_groups = ItemType.objects.exclude(group_id__in=Subquery(excluded_group_ids)).values('group_id').annotate(count=Count('type_id')).order_by('-count')[:50]
    group_ids = [g['group_id'] for g in top_groups]
    group_map = ItemGroup.objects.filter(group_id__in=group_ids).in_bulk()
    group_labels = []
    group_data = []
    group_cat_ids = []
    for g in top_groups:
        grp = group_map.get(g['group_id'])
        group_labels.append(grp.group_name if grp else f"Group {g['group_id']}")
        group_data.append(g['count'])
        group_cat_ids.append(grp.category_id if grp else 0)
    count_qs = ItemType.objects.values('group_id').annotate(cnt=Count('type_id'))
    count_map = {item['group_id']: item['cnt'] for item in count_qs}
    search_query = request.GET.get('q', '')
    all_groups_qs = ItemGroup.objects.all()
    if search_query: all_groups_qs = all_groups_qs.filter(group_name__icontains=search_query)
    processed_groups = []
    for grp in all_groups_qs:
        grp.calculated_count = count_map.get(grp.group_id, 0)
        processed_groups.append(grp)
    processed_groups.sort(key=lambda x: (-x.calculated_count, x.group_name))
    paginator = Paginator(processed_groups, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'item_count': item_count, 'group_count': group_count, 'attr_count': attr_count,
        'group_labels': group_labels, 'group_data': group_data, 'group_cat_ids': group_cat_ids,
        'groups_page': page_obj, 'search_query': search_query, 'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/sde.html', context)

@login_required
@user_passes_test(is_admin)
def management_celery(request):
    context = get_system_status()
    total_characters = EveCharacter.objects.count()
    threshold = timezone.now() - timedelta(minutes=60)
    stale_count = EveCharacter.objects.filter(last_updated__lt=threshold).count()
    invalid_token_count = 0
    for char in EveCharacter.objects.all().iterator():
        if not char.refresh_token: invalid_token_count += 1
    if total_characters > 0: esi_health_percent = int(((total_characters - stale_count) / total_characters * 100))
    else: esi_health_percent = 0
    context.update({
        'total_characters': total_characters, 'stale_count': stale_count,
        'invalid_token_count': invalid_token_count, 'esi_health_percent': esi_health_percent,
        'base_template': get_template_base(request)
    })
    context.update(get_mgmt_context(request.user))
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/celery_content.html', context)
    return render(request, 'management/celery_status.html', context)

# --- PERMISSIONS & GROUPS MANAGEMENT (Enhanced) ---

@login_required
@user_passes_test(is_admin)
def management_permissions(request):
    """
    Dynamic Access Control Matrix using Database Models.
    """
    db_caps = Capability.objects.all().prefetch_related('groups')
    # Use Priority Order
    groups = Group.objects.all().select_related('priority_config').order_by('priority_config__level', 'name')

    context = {
        'groups': groups,
        'capabilities': db_caps,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/permissions.html', context)

@login_required
@user_passes_test(is_admin)
@require_POST
def api_reorder_roles(request):
    """
    Updates the level of roles based on a list of IDs.
    """
    try:
        data = json.loads(request.body)
        ordered_ids = data.get('ordered_ids', [])
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    if not ordered_ids:
        return JsonResponse({'success': False, 'error': 'No data'})

    for index, group_id in enumerate(ordered_ids):
        try:
            group = Group.objects.get(id=group_id)
            RolePriority.objects.update_or_create(
                group=group,
                defaults={'level': index}
            )
        except Group.DoesNotExist:
            continue

    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_admin)
@require_POST
def api_permissions_toggle(request):
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        cap_id = data.get('cap_id')
    except json.JSONDecodeError: return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    group = get_object_or_404(Group, id=group_id)
    cap = get_object_or_404(Capability, id=cap_id)
    if cap.groups.filter(id=group.id).exists():
        cap.groups.remove(group)
        state = False
    else:
        cap.groups.add(group)
        state = True
    return JsonResponse({'success': True, 'new_state': state})

@login_required
@user_passes_test(is_admin)
@require_POST
def api_manage_group(request):
    try:
        data = json.loads(request.body)
        action = data.get('action')
        group_name = data.get('name', '').strip()
        group_id = data.get('id')
    except json.JSONDecodeError: return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    if action == 'create':
        if not group_name: return JsonResponse({'success': False, 'error': 'Name required'})
        if Group.objects.filter(name=group_name).exists(): return JsonResponse({'success': False, 'error': 'Group exists'})
        Group.objects.create(name=group_name)
    elif action == 'update':
        group = get_object_or_404(Group, id=group_id)
        if group_name and group_name != group.name:
            if Group.objects.filter(name=group_name).exclude(id=group_id).exists():
                return JsonResponse({'success': False, 'error': 'Name taken'})
            group.name = group_name
            group.save()
    elif action == 'delete':
        group = get_object_or_404(Group, id=group_id)
        if group.name == 'Admin': return JsonResponse({'success': False, 'error': 'Cannot delete Admin group'})
        group.delete()
    return JsonResponse({'success': True})

# --- RULE MANAGER VIEWS ---

@login_required
@user_passes_test(is_admin)
def management_rules(request):
    """
    Renders the Rule Helper Dashboard.
    """
    context = {
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/rules_helper.html', context)

@login_required
@user_passes_test(is_admin)
def api_group_search(request):
    """
    Searches for ItemGroups (e.g. "Shield Hardener")
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 3: return JsonResponse({'results': []})
    
    groups = ItemGroup.objects.filter(group_name__icontains=query, published=True)[:20]
    results = [{'id': g.group_id, 'name': g.group_name} for g in groups]
    return JsonResponse({'results': results})

@login_required
@user_passes_test(is_admin)
def api_rule_discovery(request, group_id):
    """
    The Brains:
    1. Fetches existing saved rules for this group.
    2. Scans items in this group to find 'Candidate' attributes (attributes common to these items).
    """
    group = get_object_or_404(ItemGroup, group_id=group_id)
    
    # 1. Get Existing Rules
    existing_rules = FitAnalysisRule.objects.filter(group=group).select_related('attribute')
    existing_attr_ids = set()
    rule_data = []
    
    for r in existing_rules:
        existing_attr_ids.add(r.attribute.attribute_id)
        rule_data.append({
            'attr_id': r.attribute.attribute_id,
            'name': r.attribute.display_name or r.attribute.name,
            'description': r.attribute.description,
            'is_active': True,
            'logic': r.comparison_logic,
            'tolerance': r.tolerance_percent,
            'source': 'saved'
        })

    # 2. Discover Candidates
    # Fetch up to 10 items in this group to sample their attributes
    sample_items = ItemType.objects.filter(group=group, published=True)[:10]
    
    if sample_items.exists():
        # Get all attributes for these items
        # Group by Attribute ID and count frequency
        common_attrs = TypeAttribute.objects.filter(item__in=sample_items)\
            .values('attribute_id')\
            .annotate(count=Count('item_id'))\
            .order_by('-count')
            
        # Filter for attributes that appear in at least 50% of the sample
        threshold = sample_items.count() / 2
        candidate_ids = [c['attribute_id'] for c in common_attrs if c['count'] >= threshold]
        
        # Remove ones we already have rules for
        new_ids = [aid for aid in candidate_ids if aid not in existing_attr_ids]
        
        # Fetch definitions
        definitions = AttributeDefinition.objects.filter(attribute_id__in=new_ids)
        
        # Exclude boring attributes (icons, graphic IDs, etc) usually hidden
        # This is a heuristic; might need tuning.
        for d in definitions:
            # Skip likely junk (names starting with graphic, icon, sfx)
            if any(x in d.name.lower() for x in ['graphic', 'icon', 'sound', 'radius', 'volume', 'mass', 'capacity']):
                continue
                
            rule_data.append({
                'attr_id': d.attribute_id,
                'name': d.display_name or d.name,
                'description': d.description,
                'is_active': False,
                'logic': 'higher', # Default
                'tolerance': 0.0,
                'source': 'discovery'
            })

    # Sort: Saved first, then by name
    rule_data.sort(key=lambda x: (not x['is_active'], x['name']))
    
    return JsonResponse({
        'group_id': group.group_id,
        'group_name': group.group_name,
        'rules': rule_data
    })

@login_required
@user_passes_test(is_admin)
@require_POST
def api_save_rules(request):
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        rules_payload = data.get('rules', []) # List of { attr_id, logic, tolerance }
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    group = get_object_or_404(ItemGroup, group_id=group_id)
    
    # Transaction logic: Wipe existing for this group, recreate active ones
    # This is simpler than differencing updates
    from django.db import transaction
    
    with transaction.atomic():
        # 1. Delete all rules for this group
        FitAnalysisRule.objects.filter(group=group).delete()
        
        # 2. Bulk Create new ones
        new_objects = []
        for r in rules_payload:
            attr = AttributeDefinition.objects.get(attribute_id=r['attr_id'])
            new_objects.append(FitAnalysisRule(
                group=group,
                attribute=attr,
                comparison_logic=r['logic'],
                tolerance_percent=float(r.get('tolerance', 0.0))
            ))
        
        FitAnalysisRule.objects.bulk_create(new_objects)
        
    return JsonResponse({'success': True, 'count': len(new_objects)})

# --- ROLES MANAGEMENT ---

@login_required
@user_passes_test(can_manage_roles) # Restricted to those with 'promote_demote_users'
def management_roles(request):
    char_qs = EveCharacter.objects.filter(is_main=True).select_related('user').order_by('character_name')
    paginator = Paginator(char_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = { 'page_obj': page_obj, 'roles': get_role_hierarchy(), 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/roles.html', context)

@login_required
@user_passes_test(can_manage_roles)
def api_search_users(request):
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    if not query and not role_filter: return JsonResponse({'results': []})
    if query and len(query) < 3 and not role_filter: return JsonResponse({'results': []})
    users = User.objects.all()
    if role_filter: users = users.filter(groups__name=role_filter)
    if query:
        matching_chars = EveCharacter.objects.filter(character_name__icontains=query)
        users = users.filter(characters__in=matching_chars)
    users = users.distinct()[:20]
    results = []
    for u in users:
        main_char = u.characters.filter(is_main=True).first() or u.characters.first()
        results.append({
            'id': u.id, 'username': main_char.character_name if main_char else u.username,
            'char_id': main_char.character_id if main_char else 0,
            'corp': main_char.corporation_name if main_char else "Unknown"
        })
    return JsonResponse({'results': results})

@login_required
@user_passes_test(can_manage_roles)
def api_get_user_roles(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    current_roles = list(target_user.groups.values_list('name', flat=True))
    _, req_highest_index = get_user_highest_role(request.user)
    available = []
    
    # Use Dynamic Hierarchy
    hierarchy = get_role_hierarchy()
    
    for role in hierarchy:
        # Check index in dynamic list if possible, or fallback
        try:
            role_idx = hierarchy.index(role)
            if role_idx > req_highest_index or is_admin(request.user):
                available.append(role)
        except ValueError:
            pass
            
    return JsonResponse({'user_id': target_user.id, 'current_roles': current_roles, 'available_roles': available})

@login_required
@user_passes_test(can_manage_roles)
@require_POST
def api_update_user_role(request):
    try:
        data = json.loads(request.body)
        target_user = get_object_or_404(User, pk=data['user_id'])
        role_name = data['role']
        action = data['action']
    except (KeyError, json.JSONDecodeError): return HttpResponseBadRequest("Invalid JSON")
    
    is_admin_actor = is_admin(request.user)
    if not (is_admin_actor and role_name == 'Admin'):
        if not can_manage_role(request.user, role_name): return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
    group = get_object_or_404(Group, name=role_name)
    if action == 'add':
        target_user.groups.add(group)
        if role_name == 'Admin': target_user.is_staff = True; target_user.save()
    elif action == 'remove':
        target_user.groups.remove(group)
        if role_name == 'Admin': target_user.is_staff = False; target_user.save()
    return JsonResponse({'success': True})

# --- DOCTRINES ---

def doctrine_list(request):
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'fits__ship_type', 'fits__tags', 'subcategories__fits__ship_type', 'subcategories__fits__tags',
        'subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__subcategories__fits__tags'
    )
    context = { 'categories': categories, 'base_template': get_template_base(request) }
    return render(request, 'doctrines/public_index.html', context)

def doctrine_detail_api(request, fit_id):
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    modules = []
    for mod in fit.modules.select_related('item_type').all():
        modules.append({ 'name': mod.item_type.type_name, 'quantity': mod.quantity, 'icon_id': mod.item_type.type_id })
    data = {
        'id': fit.id, 'name': fit.name, 'hull': fit.ship_type.type_name,
        'hull_id': fit.ship_type.type_id, 'description': fit.description,
        'eft_block': fit.eft_format, 'modules': modules
    }
    return JsonResponse(data)

@login_required
@user_passes_test(can_manage_doctrines)
def manage_doctrines(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            fit_id = request.POST.get('fit_id')
            DoctrineFit.objects.filter(id=fit_id).delete()
            return redirect('manage_doctrines')
        elif action == 'create' or action == 'update':
            raw_eft = request.POST.get('eft_paste')
            cat_id = request.POST.get('category_id')
            description = request.POST.get('description', '')
            tag_ids = request.POST.getlist('tags')
            parser = EFTParser(raw_eft)
            if parser.parse():
                category = get_object_or_404(DoctrineCategory, id=cat_id)
                if action == 'update':
                    fit_id = request.POST.get('fit_id')
                    fit = get_object_or_404(DoctrineFit, id=fit_id)
                    fit.name = parser.fit_name; fit.category = category; fit.ship_type = parser.hull_obj
                    fit.eft_format = parser.raw_text; fit.description = description; fit.save()
                    fit.modules.all().delete()
                else:
                    fit = DoctrineFit.objects.create(name=parser.fit_name, category=category, ship_type=parser.hull_obj, eft_format=parser.raw_text, description=description)
                if tag_ids: fit.tags.set(tag_ids)
                else: fit.tags.clear()
                for item in parser.items:
                    FitModule.objects.create(fit=fit, item_type=item['obj'], quantity=item['quantity'])
            return redirect('manage_doctrines')
    categories = DoctrineCategory.objects.all()
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'order')
    tags = DoctrineTag.objects.all()
    context = { 'categories': categories, 'fits': fits, 'tags': tags, 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/doctrines.html', context)