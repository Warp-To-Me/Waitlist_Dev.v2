from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
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
    """
    Determines whether to render the full page or just the content block.
    """
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return 'base_content.html'
    return 'base.html'

# --- Permission Helper ---
def is_management(user):
    """
    Checks if user has access to management dashboard.
    Allows Superusers OR anyone with a role higher than 'Resident'.
    """
    if user.is_superuser:
        return True
    
    # List of roles allowed to access management
    # Basically everyone in the hierarchy except 'Public' and 'Resident'
    allowed_roles = ROLE_HIERARCHY[:-2] # Exclude last two (Resident, Public)
    
    return user.groups.filter(name__in=allowed_roles).exists()

# --- Public Views ---

def landing_page(request):
    context = {
        'base_template': get_template_base(request)
    }
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
            
    esi_data = {'implants': [], 'queue': [], 'history': [], 'skill_history': []}
    grouped_skills = {}
    token_missing = False
    
    if active_char:
        # 0. Check for Missing Refresh Token
        if not active_char.refresh_token:
            token_missing = True
        else:
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

            # 4. SKILL SNAPSHOT HISTORY
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
                # Fail gracefully if migration hasn't run yet
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
                        
                        if group_name not in grouped_skills:
                            grouped_skills[group_name] = []
                        
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

    totals = characters.aggregate(
        wallet_sum=Sum('wallet_balance'),
        lp_sum=Sum('concord_lp'),
        sp_sum=Sum('total_sp')
    )
    total_wallet = totals['wallet_sum'] or 0
    total_lp = totals['lp_sum'] or 0
    total_sp = totals['sp_sum'] or 0

    context = {
        'active_char': active_char,
        'characters': characters,
        'esi': esi_data,
        'grouped_skills': grouped_skills,
        'token_missing': token_missing,
        'total_wallet': total_wallet,
        'total_lp': total_lp,
        'account_total_sp': total_sp,
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

    corp_labels = [entry['corporation_name'] for entry in corp_distribution]
    corp_data = [entry['count'] for entry in corp_distribution]

    context = {
        'total_users': User.objects.count(),
        'total_fleets': Fleet.objects.count(),
        'active_fleets_count': Fleet.objects.filter(is_active=True).count(),
        'total_characters': EveCharacter.objects.count(),
        'growth_labels': growth_labels,
        'growth_data': growth_data,
        'corp_labels': corp_labels,
        'corp_data': corp_data,
        'base_template': get_template_base(request)
    }
    return render(request, 'management/dashboard.html', context)

@login_required
@user_passes_test(is_management)
def management_users(request):
    users = User.objects.prefetch_related('characters').order_by('-last_login')[:100]
    context = {
        'users': users,
        'base_template': get_template_base(request)
    }
    return render(request, 'management/users.html', context)

@login_required
@user_passes_test(is_management)
def management_fleets(request):
    fleets = Fleet.objects.all().order_by('-created_at')[:50]
    context = {
        'fleets': fleets,
        'base_template': get_template_base(request)
    }
    return render(request, 'management/fleets.html', context)

@login_required
@user_passes_test(is_management)
def management_sde(request):
    item_count = ItemType.objects.count()
    context = {
        'item_count': item_count,
        'base_template': get_template_base(request)
    }
    return render(request, 'management/sde.html', context)

@login_required
@user_passes_test(is_management)
def management_celery(request):
    context = get_system_status()
    
    total_characters = EveCharacter.objects.count()
    threshold = timezone.now() - timedelta(minutes=60)
    stale_count = EveCharacter.objects.filter(last_updated__lt=threshold).count()
    
    invalid_token_count = 0
    for char in EveCharacter.objects.all().iterator():
        if not char.refresh_token:
            invalid_token_count += 1

    esi_health_percent = int(((total_characters - stale_count) / total_characters * 100)) if total_characters > 0 else 0

    context.update({
        'total_characters': total_characters,
        'stale_count': stale_count,
        'invalid_token_count': invalid_token_count,
        'esi_health_percent': esi_health_percent,
        'base_template': get_template_base(request)
    })
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/celery_content.html', context)
        
    return render(request, 'management/celery_status.html', context)

# --- ROLE MANAGEMENT VIEWS ---

@login_required
@user_passes_test(is_management)
def management_roles(request):
    context = {
        'base_template': get_template_base(request)
    }
    return render(request, 'management/roles.html', context)

@login_required
@user_passes_test(is_management)
def api_search_users(request):
    query = request.GET.get('q', '')
    if len(query) < 3:
        return JsonResponse({'results': []})
    
    matching_chars = EveCharacter.objects.filter(character_name__icontains=query)
    users = User.objects.filter(characters__in=matching_chars).distinct()[:10]
    
    results = []
    for u in users:
        main_char = u.characters.filter(is_main=True).first()
        if not main_char:
            main_char = u.characters.first()
            
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
    requestor = request.user
    
    current_roles = list(target_user.groups.values_list('name', flat=True))
    _, req_highest_index = get_user_highest_role(requestor)
    
    available_to_assign = []
    for role in ROLE_HIERARCHY:
        role_index = ROLE_HIERARCHY.index(role)
        # Check: Is target role strictly below my rank?
        if role_index > req_highest_index:
             available_to_assign.append(role)

    return JsonResponse({
        'user_id': target_user.id,
        'current_roles': current_roles,
        'available_roles': available_to_assign
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
        return JsonResponse({'success': False, 'error': 'Permission denied. You cannot manage this role.'}, status=403)
    
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