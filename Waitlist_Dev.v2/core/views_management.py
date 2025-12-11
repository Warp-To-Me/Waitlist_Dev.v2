import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum, Subquery, OuterRef, Q
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_POST
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

# Core Imports - Permissions
from core.permissions import (
    is_management, 
    is_fleet_command, 
    is_admin, 
    can_manage_roles,
    can_view_sensitive_data,
    can_manage_bans,
    can_view_ban_audit,
    get_mgmt_context, 
    get_template_base
)

# Core Imports - Utils
from core.utils import (
    get_system_status, 
    get_character_data, 
    can_manage_role,
    get_role_hierarchy,
    get_user_highest_role
)

from core.models import Capability, RolePriority, Ban, BanAuditLog

# Model Imports
from pilot_data.models import EveCharacter, ItemType, ItemGroup, TypeAttribute
from waitlist_data.models import Fleet, WaitlistEntry

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
    
    # Use Shared Helper
    esi_data, grouped_skills = get_character_data(active_char)
    
    totals = characters.aggregate(wallet_sum=Sum('wallet_balance'), lp_sum=Sum('concord_lp'), sp_sum=Sum('total_sp'))
    
    # Check permissions for sensitive data
    obfuscate_financials = not can_view_sensitive_data(request.user)
    
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

# --- PERMISSIONS & GROUPS MANAGEMENT ---

@login_required
@user_passes_test(is_admin)
def management_permissions(request):
    """
    Dynamic Access Control Matrix using Database Models.
    Capabilities are ordered by the 'order' field in the database.
    """
    db_caps = Capability.objects.all().prefetch_related('groups')
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

# --- ROLES MANAGEMENT ---

@login_required
@user_passes_test(can_manage_roles)
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

# --- BAN MANAGEMENT ---

@login_required
@user_passes_test(can_manage_bans)
def management_bans(request):
    # Pre-fetch Main Character Names & IDs
    user_main = EveCharacter.objects.filter(user=OuterRef('user'), is_main=True)
    issuer_main = EveCharacter.objects.filter(user=OuterRef('issuer'), is_main=True)

    bans = Ban.objects.all().select_related('user', 'issuer').annotate(
        user_char_name=Subquery(user_main.values('character_name')[:1]),
        user_char_id=Subquery(user_main.values('character_id')[:1]),
        issuer_char_name=Subquery(issuer_main.values('character_name')[:1])
    ).order_by('-created_at')

    # --- FILTERING LOGIC ---
    filter_status = request.GET.get('filter', 'all')
    now = timezone.now()

    if filter_status == 'active':
        # Expires in future OR is permanent (expires_at is null)
        bans = bans.filter(models.Q(expires_at__gt=now) | models.Q(expires_at__isnull=True))
    elif filter_status == 'expired':
        # Expires in past
        bans = bans.filter(expires_at__lt=now)
    elif filter_status == 'permanent':
        # No expiration date
        bans = bans.filter(expires_at__isnull=True)

    context = {
        'bans': bans,
        'current_filter': filter_status, # Pass to template for active state
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/bans.html', context)

@login_required
@user_passes_test(can_view_ban_audit)
def management_ban_audit(request):
    # Pre-fetch Main Character Names for Target and Actor
    target_main = EveCharacter.objects.filter(user=OuterRef('target_user'), is_main=True)
    actor_main = EveCharacter.objects.filter(user=OuterRef('actor'), is_main=True)

    logs = BanAuditLog.objects.all().select_related('target_user', 'actor', 'ban').annotate(
        target_char_name=Subquery(target_main.values('character_name')[:1]),
        actor_char_name=Subquery(actor_main.values('character_name')[:1])
    ).order_by('-timestamp')

    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/ban_audit.html', context)

@login_required
@user_passes_test(can_manage_bans)
@require_POST
def api_ban_user(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        reason = data.get('reason')
        duration = data.get('duration') # "permanent", "5m", "1h", "1d", etc. or custom date?
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if not user_id or not reason:
        return JsonResponse({'success': False, 'error': 'User and Reason required'})

    target_user = get_object_or_404(User, pk=user_id)

    # Check if already banned (Active Ban)
    active_ban = Ban.objects.filter(
        user=target_user
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
    ).exists()

    if active_ban:
         return JsonResponse({'success': False, 'error': 'User is already banned. Update existing ban.'})

    expires_at = None
    if duration and duration != 'permanent':
        try:
            minutes = int(duration)
            expires_at = timezone.now() + timedelta(minutes=minutes)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid duration format'})

    # Create Ban
    ban = Ban.objects.create(
        user=target_user,
        issuer=request.user,
        reason=reason,
        expires_at=expires_at
    )

    # Log Action
    BanAuditLog.objects.create(
        target_user=target_user,
        ban=ban,
        actor=request.user,
        action='create',
        details=f"Reason: {reason}, Expires: {expires_at or 'Never'}"
    )

    # Remove from Waitlist (WaitlistEntry)
    deleted_count, _ = WaitlistEntry.objects.filter(character__user=target_user).delete()

    return JsonResponse({'success': True})

@login_required
@user_passes_test(can_manage_bans)
@require_POST
def api_update_ban(request):
    try:
        data = json.loads(request.body)
        ban_id = data.get('ban_id')
        action = data.get('action') # 'update' or 'remove'
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    ban = get_object_or_404(Ban, id=ban_id)

    if action == 'remove':
        ban.delete()
        BanAuditLog.objects.create(
            target_user=ban.user,
            actor=request.user,
            action='remove',
            details=f"Ban removed for {ban.user.username}"
        )
        return JsonResponse({'success': True})

    elif action == 'update':
        reason = data.get('reason')
        duration = data.get('duration') # integer minutes or 'permanent'

        changes = []
        if reason and reason != ban.reason:
            changes.append(f"Reason: {ban.reason} -> {reason}")
            ban.reason = reason

        if duration is not None:
            new_expires = None
            if duration != 'permanent':
                try:
                    minutes = int(duration)
                    new_expires = timezone.now() + timedelta(minutes=minutes)
                except ValueError:
                     return JsonResponse({'success': False, 'error': 'Invalid duration'})

            if new_expires != ban.expires_at:
                 changes.append(f"Expires: {ban.expires_at} -> {new_expires}")
                 ban.expires_at = new_expires

        if changes:
            ban.save()
            BanAuditLog.objects.create(
                target_user=ban.user,
                ban=ban,
                actor=request.user,
                action='update',
                details=", ".join(changes)
            )

        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid action'})