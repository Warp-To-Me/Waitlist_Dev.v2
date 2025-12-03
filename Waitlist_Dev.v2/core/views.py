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
from core.utils import get_system_status, get_user_highest_role, can_manage_role, ROLE_HIERARCHY

# Import Celery App
from waitlist_project.celery import app as celery_app

# Import Models
from pilot_data.models import EveCharacter, ItemType, ItemGroup, SkillHistory
from waitlist_data.models import Fleet
from esi_calls.token_manager import update_character_data

# --- Helper for SPA Rendering ---
def get_template_base(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return 'base_content.html'
    return 'base.html'

# --- Permission Helpers ---
def is_management(user):
    if user.is_superuser: return True
    allowed = ROLE_HIERARCHY[:-2] 
    return user.groups.filter(name__in=allowed).exists()

def is_fleet_command(user):
    if user.is_superuser: return True
    allowed = ROLE_HIERARCHY[:8]
    return user.groups.filter(name__in=allowed).exists()

def is_admin(user):
    if user.is_superuser: return True
    return user.groups.filter(name='Admin').exists()

def get_mgmt_context(user):
    return {
        'can_view_fleets': is_fleet_command(user),
        'can_view_admin': is_admin(user)
    }

# --- Data Builder Helper ---
def _get_character_data(active_char):
    """
    Constructs the ESI data dictionary and grouped skills for a character
    purely from the database.
    """
    esi_data = {'implants': [], 'queue': [], 'history': [], 'skill_history': []}
    grouped_skills = {}
    
    if not active_char:
        return esi_data, grouped_skills

    # 1. Implants
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

    # 2. Skill Queue
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

    # 3. Corp History
    esi_data['history'] = active_char.corp_history.all().order_by('-start_date')

    # 4. Skill History
    try:
        raw_history = active_char.skill_history.all().order_by('-logged_at')[:30]
        if raw_history.exists():
            h_ids = [h.skill_id for h in raw_history]
            h_items = ItemType.objects.filter(type_id__in=h_ids).in_bulk(field_name='type_id')
            
            for h in raw_history:
                item = h_items.get(h.skill_id)
                esi_data['skill_history'].append({
                    'name': item.type_name if item else f"Unknown Skill {h.skill_id}",
                    'old_level': h.old_level,
                    'new_level': h.new_level,
                    'sp_diff': h.new_sp - h.old_sp,
                    'logged_at': h.logged_at
                })
    except Exception:
        pass

    # 5. Skills
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
                    'name': item.type_name,
                    'level': s.active_skill_level,
                    'sp': s.skillpoints_in_skill
                })
        
        for g in grouped_skills:
            grouped_skills[g].sort(key=lambda x: x['name'])
        grouped_skills = dict(sorted(grouped_skills.items()))

    # 6. Ship
    if active_char.current_ship_type_id:
            try:
                ship_item = ItemType.objects.get(type_id=active_char.current_ship_type_id)
                active_char.ship_type_name = ship_item.type_name
            except ItemType.DoesNotExist:
                active_char.ship_type_name = "Unknown Hull"
    
    return esi_data, grouped_skills

# --- Public Views ---

def landing_page(request):
    context = { 'base_template': get_template_base(request) }
    return render(request, 'landing.html', context)

# --- Profile & Alt Management ---

@login_required
def profile_view(request):
    characters = request.user.characters.all()
    active_char_id = request.session.get('active_char_id')
    
    if active_char_id:
        active_char = characters.filter(character_id=active_char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char and characters.exists():
            active_char = characters.first()
            
    # Use Helper
    esi_data, grouped_skills = _get_character_data(active_char)
    
    token_missing = False
    if active_char and not active_char.refresh_token:
        token_missing = True

    totals = characters.aggregate(
        wallet_sum=Sum('wallet_balance'),
        lp_sum=Sum('concord_lp'),
        sp_sum=Sum('total_sp')
    )

    context = {
        'active_char': active_char,
        'characters': characters,
        'esi': esi_data,
        'grouped_skills': grouped_skills,
        'token_missing': token_missing,
        'total_wallet': totals['wallet_sum'] or 0,
        'total_lp': totals['lp_sum'] or 0,
        'account_total_sp': totals['sp_sum'] or 0,
        'base_template': get_template_base(request) 
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/profile_content.html', context)

    return render(request, 'profile.html', context)

@login_required
def api_refresh_profile(request, char_id):
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    if not character.refresh_token:
        return JsonResponse({'success': False, 'error': 'No refresh token'})
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

# --- MANAGEMENT VIEWS ---

@login_required
@user_passes_test(is_management)
def management_dashboard(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    user_growth = User.objects.filter(date_joined__gte=thirty_days_ago) \
        .annotate(date=TruncDate('date_joined')) \
        .values('date') \
        .annotate(count=Count('id')) \
        .order_by('date')

    growth_labels = [entry['date'].strftime('%b %d') for entry in user_growth]
    growth_data = [entry['count'] for entry in user_growth]

    corp_distribution = EveCharacter.objects.values('corporation_name') \
        .annotate(count=Count('id')) \
        .order_by('-count')[:5]

    context = {
        'total_users': User.objects.count(),
        'total_fleets': Fleet.objects.count(),
        'active_fleets_count': Fleet.objects.filter(is_active=True).count(),
        'total_characters': EveCharacter.objects.count(),
        'growth_labels': growth_labels,
        'growth_data': growth_data,
        'corp_labels': [e['corporation_name'] for e in corp_distribution],
        'corp_data': [e['count'] for e in corp_distribution],
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/dashboard.html', context)

@login_required
@user_passes_test(is_fleet_command) # UPDATED: Restricted to FC+
def management_users(request):
    """
    Searchable Character Directory with Linked Character Counts & Main Character info.
    """
    query = request.GET.get('q', '')
    
    # Subquery to fetch the name of the 'Main' character for the user owning the row's character
    # This avoids N+1 queries when displaying the "Main" column.
    main_name_sq = EveCharacter.objects.filter(
        user=OuterRef('user'),
        is_main=True
    ).values('character_name')[:1]

    # 1. Base Query with Annotations
    char_qs = EveCharacter.objects.select_related('user').annotate(
        # Count all characters belonging to this user
        linked_count=Count('user__characters', distinct=True),
        # Attach the Main Character's name
        main_char_name=Subquery(main_name_sq)
    ).order_by('character_name')
    
    # 2. Search
    if query:
        char_qs = char_qs.filter(character_name__icontains=query)

    # 3. Pagination (UPDATED: 10 per page)
    paginator = Paginator(char_qs, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/users.html', context)

@login_required
@user_passes_test(is_fleet_command) # RESTRICTED: FC+
def management_user_inspect(request, user_id, char_id=None):
    """
    Replica Profile View (Read-Only)
    """
    target_user = get_object_or_404(User, pk=user_id)
    characters = target_user.characters.all()
    
    if char_id:
        active_char = characters.filter(character_id=char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char:
            active_char = characters.first()
            
    # Use Helper
    esi_data, grouped_skills = _get_character_data(active_char)
    
    totals = characters.aggregate(
        wallet_sum=Sum('wallet_balance'),
        lp_sum=Sum('concord_lp'),
        sp_sum=Sum('total_sp')
    )

    # Obfuscation Logic
    obfuscate_financials = not is_admin(request.user)

    context = {
        'active_char': active_char,
        'characters': characters,
        'esi': esi_data,
        'grouped_skills': grouped_skills,
        'token_missing': False, # Suppress warning in inspect mode
        'total_wallet': totals['wallet_sum'] or 0,
        'total_lp': totals['lp_sum'] or 0,
        'account_total_sp': totals['sp_sum'] or 0,
        
        # Inspection Flags
        'is_inspection_mode': True,
        'inspect_user_id': target_user.id,
        'obfuscate_financials': obfuscate_financials,
        
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))

    # Support partial loading for switching tabs/characters within inspection
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/profile_content.html', context)

    # Reuse the standard profile template but with injected context
    return render(request, 'profile.html', context)

@login_required
@user_passes_test(is_fleet_command)
def management_fleets(request):
    fleets = Fleet.objects.all().order_by('-created_at')[:50]
    context = {
        'fleets': fleets,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/fleets.html', context)

@login_required
@user_passes_test(is_admin)
def management_sde(request):
    item_count = ItemType.objects.count()
    context = {
        'item_count': item_count,
        'base_template': get_template_base(request)
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
        if not char.refresh_token:
            invalid_token_count += 1
    if total_characters > 0:
        esi_health_percent = int(((total_characters - stale_count) / total_characters * 100))
    else:
        esi_health_percent = 0
    context.update({
        'total_characters': total_characters,
        'stale_count': stale_count,
        'invalid_token_count': invalid_token_count,
        'esi_health_percent': esi_health_percent,
        'base_template': get_template_base(request)
    })
    context.update(get_mgmt_context(request.user))
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/celery_content.html', context)
    return render(request, 'management/celery_status.html', context)

@login_required
@user_passes_test(is_management)
def management_roles(request):
    context = { 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/roles.html', context)

# --- API Endpoints ---
@login_required
@user_passes_test(is_management)
def api_search_users(request):
    query = request.GET.get('q', '')
    if len(query) < 3: return JsonResponse({'results': []})
    matching_chars = EveCharacter.objects.filter(character_name__icontains=query)
    users = User.objects.filter(characters__in=matching_chars).distinct()[:10]
    results = []
    for u in users:
        main_char = u.characters.filter(is_main=True).first() or u.characters.first()
        results.append({
            'id': u.id,
            'username': main_char.character_name if main_char else u.username,
            'char_id': main_char.character_id if main_char else 0,
            'corp': main_char.corporation_name if main_char else "Unknown"
        })
    return JsonResponse({'results': results})

@login_required
@user_passes_test(is_management)
def api_get_user_roles(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    current_roles = list(target_user.groups.values_list('name', flat=True))
    _, req_highest_index = get_user_highest_role(request.user)
    available = []
    for role in ROLE_HIERARCHY:
        if ROLE_HIERARCHY.index(role) > req_highest_index:
             available.append(role)
    return JsonResponse({
        'user_id': target_user.id,
        'current_roles': current_roles,
        'available_roles': available
    })

@login_required
@user_passes_test(is_management)
@require_POST
def api_update_user_role(request):
    try:
        data = json.loads(request.body)
        target_user = get_object_or_404(User, pk=data['user_id'])
        role_name = data['role']
        action = data['action']
    except (KeyError, json.JSONDecodeError):
        return HttpResponseBadRequest("Invalid JSON")
    if not can_manage_role(request.user, role_name):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    group = get_object_or_404(Group, name=role_name)
    if action == 'add':
        target_user.groups.add(group)
        if role_name == 'Admin':
            target_user.is_staff = True
            target_user.save()
    elif action == 'remove':
        target_user.groups.remove(group)
        if role_name == 'Admin':
            target_user.is_staff = False
            target_user.save()
    return JsonResponse({'success': True})