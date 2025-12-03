from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from core.utils import get_system_status  # Import the new helper

# Import Celery App
from waitlist_project.celery import app as celery_app

from pilot_data.models import EveCharacter, ItemType, ItemGroup
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

# --- Public Views ---

def landing_page(request):
    context = {
        'base_template': get_template_base(request)
    }
    return render(request, 'landing.html', context)

# --- Profile & Alt Management ---

@login_required
def profile_view(request):
    """
    Loads profile from DATABASE only.
    Supports partial rendering for AJAX refreshes.
    """
    characters = request.user.characters.all()
    active_char_id = request.session.get('active_char_id')
    
    if active_char_id:
        active_char = characters.filter(character_id=active_char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char and characters.exists():
            active_char = characters.first()
            
    esi_data = {'implants': [], 'queue': [], 'history': []}
    grouped_skills = {}
    token_missing = False
    
    if active_char:
        # 0. Check for Missing Refresh Token (Fix for legacy characters)
        if not active_char.refresh_token:
            token_missing = True
        else:
            # 1. Implants from DB
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

            # 2. Skill Queue from DB
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

            # 3. History from DB
            esi_data['history'] = active_char.corp_history.all().order_by('-start_date')

            # 4. Skills from DB (Grouping)
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

            # 5. Ship Name Lookup
            if active_char.current_ship_type_id:
                 try:
                     ship_item = ItemType.objects.get(type_id=active_char.current_ship_type_id)
                     active_char.ship_type_name = ship_item.type_name
                 except ItemType.DoesNotExist:
                     active_char.ship_type_name = "Unknown Hull"

    # Calculate Totals using DB Aggregation
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
        'token_missing': token_missing,  # Pass flag to template
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

def is_management(user):
    return user.groups.filter(name='Management').exists() or user.is_superuser

# --- MANAGEMENT VIEWS ---

@login_required
@user_passes_test(is_management)
def management_dashboard(request):
    # --- ESI / Token Statistics ---
    total_characters = EveCharacter.objects.count()
    
    threshold = timezone.now() - timedelta(minutes=60)
    stale_count = EveCharacter.objects.filter(last_updated__lt=threshold).count()
    
    # FIX: EncryptedTextField does not support database-level filtering (exact/isnull).
    # We must iterate in Python to check validity. Using iterator() for memory safety.
    invalid_token_count = 0
    for char in EveCharacter.objects.all().iterator():
        if not char.refresh_token:
            invalid_token_count += 1
    
    # --- SDE Statistics ---
    sde_items_count = ItemType.objects.count()
    sde_groups_count = ItemGroup.objects.count()
    sde_status = "ONLINE" if sde_items_count > 0 else "OFFLINE"

    context = {
        'total_users': User.objects.count(),
        'total_fleets': Fleet.objects.count(),
        'active_fleets_count': Fleet.objects.filter(is_active=True).count(),
        'total_characters': total_characters,
        'stale_count': stale_count,
        'invalid_token_count': invalid_token_count,
        'esi_health_percent': int(((total_characters - stale_count) / total_characters * 100)) if total_characters > 0 else 0,
        'sde_status': sde_status,
        'sde_items_count': sde_items_count,
        'sde_groups_count': sde_groups_count,
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
    # Use the shared helper function
    context = get_system_status()
    context['base_template'] = get_template_base(request)
    
    # Handle Partial Render (For HTTP fallback or initial load)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('partial') == 'true':
        return render(request, 'partials/celery_content.html', context)
        
    return render(request, 'management/celery_status.html', context)