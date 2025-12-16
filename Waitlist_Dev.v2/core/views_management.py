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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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

# Decorator Helper
def check_permission(perm_func):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not perm_func(request.user):
                return Response({'error': 'Permission Denied'}, status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

@api_view(['GET'])
@check_permission(is_management)
def management_dashboard(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    user_growth = User.objects.filter(date_joined__gte=thirty_days_ago).annotate(date=TruncDate('date_joined')).values('date').annotate(count=Count('id')).order_by('date')
    growth_labels = [entry['date'].strftime('%b %d') for entry in user_growth]
    growth_data = [entry['count'] for entry in user_growth]
    corp_distribution = EveCharacter.objects.values('corporation_name').annotate(count=Count('id')).order_by('-count')[:5]
    
    return Response({
        'stats': {
            'total_users': User.objects.count(), 
            'total_fleets': Fleet.objects.count(),
            'active_fleets_count': Fleet.objects.filter(is_active=True).count(), 
            'total_characters': EveCharacter.objects.count()
        },
        'charts': {
            'growth_labels': growth_labels, 
            'growth_data': growth_data,
            'corp_labels': [e['corporation_name'] for e in corp_distribution],
            'corp_data': [e['count'] for e in corp_distribution],
        }
    })

@api_view(['GET'])
@check_permission(is_fleet_command)
def management_users(request):
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'character')
    direction = request.GET.get('dir', 'asc')
    page_number = request.GET.get('page', 1)
    
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
    page_obj = paginator.get_page(page_number)
    
    results = []
    for char in page_obj:
        results.append({
            'id': char.user.id,
            'character_name': char.character_name,
            'character_id': char.character_id,
            'main_character_name': char.main_char_name or "N/A",
            'corporation_name': char.corporation_name,
            'alliance_name': char.alliance_name,
            'linked_count': char.linked_count,
            'last_updated': char.last_updated
        })

    return Response({
        'users': results,
        'pagination': {
            'current': page_obj.number,
            'total': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous()
        }
    })

@api_view(['GET'])
@check_permission(is_fleet_command)
def management_user_inspect(request, user_id, char_id=None):
    target_user = get_object_or_404(User, pk=user_id)
    characters = target_user.characters.all()
    if char_id: active_char = characters.filter(character_id=char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char: active_char = characters.filter(is_main=True).first()
        if not active_char and characters.exists(): active_char = characters.first()
    
    esi_data, grouped_skills = None, None
    if active_char:
        # Use Shared Helper
        esi_data, grouped_skills = get_character_data(active_char)
    
    totals = characters.aggregate(wallet_sum=Sum('wallet_balance'), lp_sum=Sum('concord_lp'), sp_sum=Sum('total_sp'))
    
    # Check permissions for sensitive data
    obfuscate_financials = not can_view_sensitive_data(request.user)
    
    char_list = [{
        'character_id': c.character_id,
        'character_name': c.character_name,
        'is_main': c.is_main,
        'corporation_name': c.corporation_name,
        'alliance_name': c.alliance_name
    } for c in characters]
    
    return Response({
        'active_char': {
            'character_id': active_char.character_id,
            'character_name': active_char.character_name,
            'corporation_name': active_char.corporation_name,
            'alliance_name': active_char.alliance_name,
        } if active_char else None,
        'characters': char_list,
        'esi_data': esi_data,
        'grouped_skills': grouped_skills,
        'totals': {
            'wallet': totals['wallet_sum'] or 0,
            'lp': totals['lp_sum'] or 0,
            'sp': totals['sp_sum'] or 0
        },
        'obfuscate_financials': obfuscate_financials,
        'inspect_user_id': target_user.id,
        'username': target_user.username
    })

@api_view(['POST'])
@check_permission(is_admin)
def api_unlink_alt(request):
    char_id = request.data.get('character_id')
    if not char_id: return Response({'success': False, 'error': 'Character ID required'}, status=400)
    
    char = get_object_or_404(EveCharacter, character_id=char_id)
    if char.is_main: return Response({'success': False, 'error': 'Cannot unlink a Main Character.'}, status=400)
    
    char.delete()
    return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_promote_alt(request):
    char_id = request.data.get('character_id')
    if not char_id: return Response({'success': False, 'error': 'Character ID required'}, status=400)
    
    target_char = get_object_or_404(EveCharacter, character_id=char_id)
    target_user = target_char.user
    is_owner = (target_user == request.user)
    is_admin_user = is_admin(request.user)
    
    if not is_owner and not is_admin_user: return Response({'success': False, 'error': 'Permission denied.'}, status=403)
    if target_char.is_main: return Response({'success': False, 'error': 'Character is already main.'}, status=400)
    
    target_user.characters.update(is_main=False)
    target_char.is_main = True
    target_char.save()
    
    if is_owner: request.session['active_char_id'] = target_char.character_id
    return Response({'success': True})

@api_view(['GET', 'POST', 'DELETE'])
@check_permission(is_fleet_command)
def management_fleets(request):
    if request.method == 'POST':
        action = request.data.get('action')
        if action == 'create':
            name = request.data.get('name')
            if name: Fleet.objects.create(name=name, commander=request.user, is_active=True)
            return Response({'status': 'created'})
        elif action == 'close':
            fleet_id = request.data.get('fleet_id')
            fleet = get_object_or_404(Fleet, id=fleet_id)
            fleet.is_active = False
            fleet.save()
            return Response({'status': 'closed'})
        elif action == 'delete':
            fleet_id = request.data.get('fleet_id')
            if is_admin(request.user): 
                Fleet.objects.filter(id=fleet_id).delete()
                return Response({'status': 'deleted'})
            else:
                return Response({'error': 'Permission denied'}, status=403)
                
    fleets = Fleet.objects.all().order_by('-is_active', '-created_at')[:50]
    data = []
    for f in fleets:
        data.append({
            'id': f.id,
            'name': f.name or f.type,
            'join_token': f.join_token,
            'commander': f.commander.username,
            'is_active': f.is_active,
            'created_at': f.created_at,
            'member_count': f.entries.count()
        })
    return Response({'fleets': data})

@api_view(['GET'])
@check_permission(is_admin)
def management_sde(request):
    item_count = ItemType.objects.count()
    group_count = ItemGroup.objects.count()
    attr_count = TypeAttribute.objects.count()
    
    # ... (Logic identical to original, just JSON serialization)
    EXCLUDED_CATEGORIES = [2, 9, 11, 17, 20, 25, 30, 40, 46, 63, 91, 2118, 350001]
    excluded_group_ids = ItemGroup.objects.filter(category_id__in=EXCLUDED_CATEGORIES).values_list('group_id', flat=True)
    top_groups = ItemType.objects.exclude(group_id__in=Subquery(excluded_group_ids)).values('group_id').annotate(count=Count('type_id')).order_by('-count')[:50]
    group_ids = [g['group_id'] for g in top_groups]
    group_map = ItemGroup.objects.filter(group_id__in=group_ids).in_bulk()
    group_labels = []
    group_data = []
    
    for g in top_groups:
        grp = group_map.get(g['group_id'])
        group_labels.append(grp.group_name if grp else f"Group {g['group_id']}")
        group_data.append(g['count'])
        
    return Response({
        'counts': {'items': item_count, 'groups': group_count, 'attrs': attr_count},
        'chart': {'labels': group_labels, 'data': group_data}
    })

@api_view(['GET'])
@check_permission(is_admin)
def management_celery(request):
    context = get_system_status() # { 'redis_latency': ..., 'active_workers': ... }
    total_characters = EveCharacter.objects.count()
    threshold = timezone.now() - timedelta(minutes=60)
    stale_count = EveCharacter.objects.filter(last_updated__lt=threshold).count()
    invalid_token_count = EveCharacter.objects.filter(refresh_token__isnull=True).count() # Simplified check
    
    if total_characters > 0: esi_health_percent = int(((total_characters - stale_count) / total_characters * 100))
    else: esi_health_percent = 0
    
    context.update({
        'total_characters': total_characters, 
        'stale_count': stale_count,
        'invalid_token_count': invalid_token_count, 
        'esi_health_percent': esi_health_percent
    })
    return Response(context)

# --- PERMISSIONS & GROUPS MANAGEMENT ---

@api_view(['GET'])
@check_permission(is_admin)
def management_permissions(request):
    db_caps = Capability.objects.all().prefetch_related('groups')
    groups = Group.objects.all().select_related('priority_config').prefetch_related('capabilities').order_by('priority_config__level', 'name')
    
    caps_data = []
    for cap in db_caps:
        caps_data.append({
            'id': cap.id,
            'name': cap.name,
            'description': cap.description,
            'groups': [g.id for g in cap.groups.all()]
        })
        
    groups_data = []
    for g in groups:
        groups_data.append({
            'id': g.id,
            'name': g.name,
            'level': g.priority_config.level if hasattr(g, 'priority_config') else 999,
            'capabilities': [c.id for c in g.capabilities.all()]
        })

    return Response({
        'groups': groups_data,
        'capabilities': caps_data
    })

@api_view(['POST'])
@check_permission(is_admin)
def api_reorder_roles(request):
    ordered_ids = request.data.get('ordered_ids', [])
    if not ordered_ids: return Response({'success': False, 'error': 'No data'}, status=400)

    for index, group_id in enumerate(ordered_ids):
        try:
            group = Group.objects.get(id=group_id)
            RolePriority.objects.update_or_create(
                group=group,
                defaults={'level': index}
            )
        except Group.DoesNotExist:
            continue
    return Response({'success': True})

@api_view(['POST'])
@check_permission(is_admin)
def api_permissions_toggle(request):
    group_id = request.data.get('group_id')
    cap_id = request.data.get('cap_id')
    
    group = get_object_or_404(Group, id=group_id)
    cap = get_object_or_404(Capability, id=cap_id)
    
    if cap.groups.filter(id=group.id).exists():
        cap.groups.remove(group)
        state = False
    else:
        cap.groups.add(group)
        state = True
    return Response({'success': True, 'new_state': state})

@api_view(['POST'])
@check_permission(is_admin)
def api_manage_group(request):
    action = request.data.get('action')
    group_name = request.data.get('name', '').strip()
    group_id = request.data.get('id')
    
    if action == 'create':
        if not group_name: return Response({'success': False, 'error': 'Name required'}, status=400)
        if Group.objects.filter(name=group_name).exists(): return Response({'success': False, 'error': 'Group exists'}, status=400)
        Group.objects.create(name=group_name)
        
    elif action == 'update':
        group = get_object_or_404(Group, id=group_id)
        if group_name and group_name != group.name:
            if Group.objects.filter(name=group_name).exclude(id=group_id).exists():
                return Response({'success': False, 'error': 'Name taken'}, status=400)
            group.name = group_name
            group.save()
            
    elif action == 'delete':
        group = get_object_or_404(Group, id=group_id)
        if group.name == 'Admin': return Response({'success': False, 'error': 'Cannot delete Admin group'}, status=400)
        group.delete()
        
    return Response({'success': True})

# --- ROLES MANAGEMENT ---

@api_view(['GET'])
@check_permission(can_manage_roles)
def management_roles(request):
    # Just return list of roles and hierarchy info
    # The frontend will fetch users via search
    return Response({
        'roles': get_role_hierarchy()
    })

@api_view(['GET'])
@check_permission(can_manage_roles)
def api_search_users(request):
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    
    if not query and not role_filter: return Response({'results': []})
    if query and len(query) < 3 and not role_filter: return Response({'results': []})
    
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
            'id': u.id, 
            'username': main_char.character_name if main_char else u.username,
            'char_id': main_char.character_id if main_char else 0,
            'corp': main_char.corporation_name if main_char else "Unknown"
        })
    return Response({'results': results})

@api_view(['GET'])
@check_permission(can_manage_roles)
def api_get_user_roles(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    current_roles = list(target_user.groups.values_list('name', flat=True))
    _, req_highest_index = get_user_highest_role(request.user)
    available = []
    
    hierarchy = get_role_hierarchy()
    for role in hierarchy:
        try:
            role_idx = hierarchy.index(role)
            if role_idx > req_highest_index or is_admin(request.user):
                available.append(role)
        except ValueError: pass
            
    return Response({'user_id': target_user.id, 'current_roles': current_roles, 'available_roles': available})

@api_view(['POST'])
@check_permission(can_manage_roles)
def api_update_user_role(request):
    target_user = get_object_or_404(User, pk=request.data.get('user_id'))
    role_name = request.data.get('role')
    action = request.data.get('action')
    
    is_admin_actor = is_admin(request.user)
    if not (is_admin_actor and role_name == 'Admin'):
        if not can_manage_role(request.user, role_name): 
            return Response({'success': False, 'error': 'Permission denied.'}, status=403)
        
    group = get_object_or_404(Group, name=role_name)
    if action == 'add':
        target_user.groups.add(group)
        if role_name == 'Admin': target_user.is_staff = True; target_user.save()
    elif action == 'remove':
        target_user.groups.remove(group)
        if role_name == 'Admin': target_user.is_staff = False; target_user.save()
        
    return Response({'success': True})

# --- BAN MANAGEMENT ---

@api_view(['GET'])
@check_permission(can_manage_bans)
def management_bans(request):
    user_main = EveCharacter.objects.filter(user=OuterRef('user'), is_main=True)
    issuer_main = EveCharacter.objects.filter(user=OuterRef('issuer'), is_main=True)

    bans = Ban.objects.all().select_related('user', 'issuer').annotate(
        user_char_name=Subquery(user_main.values('character_name')[:1]),
        user_char_id=Subquery(user_main.values('character_id')[:1]),
        issuer_char_name=Subquery(issuer_main.values('character_name')[:1])
    ).order_by('-created_at')

    filter_status = request.GET.get('filter', 'all')
    now = timezone.now()

    if filter_status == 'active':
        bans = bans.filter(models.Q(expires_at__gt=now) | models.Q(expires_at__isnull=True))
    elif filter_status == 'expired':
        bans = bans.filter(expires_at__lt=now)
    elif filter_status == 'permanent':
        bans = bans.filter(expires_at__isnull=True)
        
    results = []
    for b in bans:
        results.append({
            'id': b.id,
            'user_id': b.user.id,
            'user_name': b.user_char_name or b.user.username,
            'user_char_id': b.user_char_id,
            'issuer_name': b.issuer_char_name or (b.issuer.username if b.issuer else "System"),
            'reason': b.reason,
            'created_at': b.created_at,
            'expires_at': b.expires_at,
            'is_active': (b.expires_at is None or b.expires_at > now)
        })

    return Response({'bans': results})

@api_view(['GET'])
@check_permission(can_view_ban_audit)
def management_ban_audit(request):
    target_main = EveCharacter.objects.filter(user=OuterRef('target_user'), is_main=True)
    actor_main = EveCharacter.objects.filter(user=OuterRef('actor'), is_main=True)

    logs = BanAuditLog.objects.all().select_related('target_user', 'actor', 'ban').annotate(
        target_char_name=Subquery(target_main.values('character_name')[:1]),
        actor_char_name=Subquery(actor_main.values('character_name')[:1])
    ).order_by('-timestamp')

    try:
        limit = int(request.GET.get('limit', 20))
    except ValueError:
        limit = 20
    if limit not in [10, 25, 50, 100]: limit = 20
    
    paginator = Paginator(logs, limit)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    results = []
    for log in page_obj:
        results.append({
            'timestamp': log.timestamp,
            'action': log.action,
            'target_name': log.target_char_name or (log.target_user.username if log.target_user else "Unknown User"),
            'actor_name': log.actor_char_name or (log.actor.username if log.actor else "System"),
            'details': log.details
        })

    return Response({
        'logs': results,
        'pagination': {'total': paginator.num_pages, 'current': page_obj.number}
    })

@api_view(['POST'])
@check_permission(can_manage_bans)
def api_ban_user(request):
    user_id = request.data.get('user_id')
    reason = request.data.get('reason')
    duration = request.data.get('duration')
    
    if not user_id or not reason: return Response({'success': False, 'error': 'User and Reason required'}, status=400)
    
    target_user = get_object_or_404(User, pk=user_id)
    active_ban = Ban.objects.filter(user=target_user).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())).exists()
    
    if active_ban: return Response({'success': False, 'error': 'User is already banned.'}, status=400)
    
    expires_at = None
    if duration and duration != 'permanent':
        try:
            minutes = int(duration)
            expires_at = timezone.now() + timedelta(minutes=minutes)
        except ValueError: return Response({'success': False, 'error': 'Invalid duration format'}, status=400)
        
    ban = Ban.objects.create(user=target_user, issuer=request.user, reason=reason, expires_at=expires_at)
    BanAuditLog.objects.create(target_user=target_user, ban=ban, actor=request.user, action='create', details=f"Reason: {reason}, Expires: {expires_at or 'Never'}")
    WaitlistEntry.objects.filter(character__user=target_user).delete()
    
    return Response({'success': True})

@api_view(['POST'])
@check_permission(can_manage_bans)
def api_update_ban(request):
    ban_id = request.data.get('ban_id')
    action = request.data.get('action')
    
    ban = get_object_or_404(Ban, id=ban_id)
    
    if action == 'remove':
        ban.delete()
        BanAuditLog.objects.create(target_user=ban.user, actor=request.user, action='remove', details=f"Ban removed for {ban.user.username}")
        return Response({'success': True})
        
    elif action == 'update':
        reason = request.data.get('reason')
        duration = request.data.get('duration')
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
                except ValueError: return Response({'success': False, 'error': 'Invalid duration'}, status=400)
            if new_expires != ban.expires_at:
                changes.append(f"Expires: {ban.expires_at} -> {new_expires}")
                ban.expires_at = new_expires
        
        if changes:
            ban.save()
            BanAuditLog.objects.create(target_user=ban.user, ban=ban, actor=request.user, action='update', details=", ".join(changes))
        return Response({'success': True})
        
    return Response({'success': False, 'error': 'Invalid action'}, status=400)