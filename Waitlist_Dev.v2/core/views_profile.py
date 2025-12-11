import json
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings
from itertools import chain # Needed for merging lists efficiently

# Core Imports
from core.permissions import get_template_base, is_fleet_command, is_admin
from core.utils import get_character_data
from core.models import BanAuditLog # Import BanAuditLog

# Models & Services
from pilot_data.models import EveCharacter
from waitlist_data.models import FleetActivity
from waitlist_data.stats import calculate_pilot_stats
from esi_calls.token_manager import update_character_data

@login_required
def profile_view(request):
    characters = request.user.characters.all()
    active_char_id = request.session.get('active_char_id')
    if active_char_id: active_char = characters.filter(character_id=active_char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char and characters.exists(): active_char = characters.first()
        
    # Use Shared Helper
    esi_data, grouped_skills = get_character_data(active_char)
    
    # --- Service Record Stats ---
    service_record = calculate_pilot_stats(active_char)
    
    # 1. Fetch Fleet Logs
    fleet_logs = FleetActivity.objects.filter(character=active_char)\
        .select_related('fleet', 'actor').order_by('-timestamp')[:50]

    # 2. Fetch Ban Logs (Targeting the User account)
    # We assume 'active_char' belongs to the user we want to see bans for.
    ban_logs = BanAuditLog.objects.filter(target_user=active_char.user)\
        .select_related('actor').order_by('-timestamp')[:20]

    # 3. Merge & Sort
    # We combine them into a single list sorted by timestamp descending
    combined_logs = sorted(
        chain(fleet_logs, ban_logs),
        key=lambda x: x.timestamp,
        reverse=True
    )[:50] # Keep the top 50 most recent combined events

    service_record['history_logs'] = combined_logs
    
    # Convert hull dict to sorted list for template
    service_record['hull_breakdown'] = sorted(
        service_record['hull_breakdown'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    token_missing = False
    if active_char and not active_char.refresh_token: token_missing = True
    
    # --- Scope Validation Check ---
    scopes_missing = False
    if active_char and active_char.access_token and is_fleet_command(request.user):
        try:
            parts = active_char.access_token.split('.')
            if len(parts) == 3:
                padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(padded).decode('utf-8'))
                current_scopes = payload.get('scp', [])
                if isinstance(current_scopes, str): current_scopes = [current_scopes]
                current_scopes_set = set(current_scopes)
                required_fc = set(settings.EVE_SCOPES_FC.split())
                if not required_fc.issubset(current_scopes_set):
                    scopes_missing = True
        except Exception as e:
            print(f"Error checking scopes: {e}")
            pass

    totals = characters.aggregate(wallet_sum=Sum('wallet_balance'), lp_sum=Sum('concord_lp'), sp_sum=Sum('total_sp'))
    context = {
        'active_char': active_char, 'characters': characters,
        'esi': esi_data, 'grouped_skills': grouped_skills, 
        'service_record': service_record,
        'token_missing': token_missing,
        'scopes_missing': scopes_missing,
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

@login_required
@require_POST
def api_toggle_xup_visibility(request):
    try:
        data = json.loads(request.body)
        char_id = data.get('character_id')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    if not char_id:
        return JsonResponse({'success': False, 'error': 'Character ID required'})

    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    character.x_up_visible = not character.x_up_visible
    character.save(update_fields=['x_up_visible'])
    
    return JsonResponse({
        'success': True, 
        'character_id': character.character_id, 
        'new_state': character.x_up_visible
    })