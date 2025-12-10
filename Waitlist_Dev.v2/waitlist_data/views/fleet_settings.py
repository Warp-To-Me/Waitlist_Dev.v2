import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.permissions import is_fleet_command, get_template_base, get_mgmt_context
from waitlist_data.models import Fleet
from esi_calls.fleet_service import get_fleet_composition, sync_fleet_structure, update_fleet_settings, ESI_BASE
from esi_calls.token_manager import check_token

@login_required
@user_passes_test(is_fleet_command)
def fleet_settings(request, token):
    """
    Manage an active fleet's MOTD and Structure.
    """
    fleet = get_object_or_404(Fleet, join_token=token)
    if not fleet.is_active:
        return redirect('fleet_history', token=token)
        
    fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
    
    # PRE-FETCH CURRENT STRUCTURE
    initial_structure = "[]"
    if fleet.esi_fleet_id and check_token(fc_char):
        comp, err = get_fleet_composition(fleet.esi_fleet_id, fc_char)
        if comp:
            # Sort wings by ID to keep order stable if not ordered by name
            raw_wings = comp.get('wings', [])
            raw_wings.sort(key=lambda x: x['id'])
            
            clean_struct = []
            for w in raw_wings:
                squads = [s['name'] for s in sorted(w.get('squads', []), key=lambda x: x['id'])]
                clean_struct.append({
                    'name': w['name'],
                    'squads': squads
                })
            initial_structure = json.dumps(clean_struct)

    context = {
        'fleet': fleet,
        'fc_char': fc_char,
        'initial_structure': initial_structure,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'waitlist/fleet_settings.html', context)

@login_required
@user_passes_test(is_fleet_command)
@require_POST
def api_update_fleet_settings(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    try:
        data = json.loads(request.body)
        motd = data.get('motd')
        structure = data.get('structure') # List of Wings
        
        fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
        
        if not fc_char: return JsonResponse({'success': False, 'error': 'No FC Character found'})
        
        messages = []
        
        # 1. Update MOTD
        if motd is not None and motd != fleet.motd:
            success, msg = update_fleet_settings(fleet.esi_fleet_id, fc_char, motd=motd)
            if success:
                fleet.motd = motd
                fleet.save()
                messages.append("MOTD updated")
            else:
                return JsonResponse({'success': False, 'error': msg})

        # 2. Update Structure
        if structure is not None:
            success, logs = sync_fleet_structure(fleet.esi_fleet_id, fc_char, structure)
            if success:
                if logs: messages.append(f"Structure synced ({len(logs)} changes)")
            else:
                return JsonResponse({'success': False, 'error': f"Structure sync failed: {logs}"})

        return JsonResponse({'success': True, 'message': ", ".join(messages) or "No changes"})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(is_fleet_command)
@require_POST
def api_link_esi_fleet(request, token):
    """
    Attempts to find the FC's current fleet in-game and link it to this Waitlist Fleet.
    Useful for bringing an "Offline Mode" fleet Online.
    """
    fleet = get_object_or_404(Fleet, join_token=token)
    
    if fleet.esi_fleet_id:
        return JsonResponse({'success': False, 'error': 'Fleet is already linked to ESI.'})

    fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
    if not fc_char: 
        return JsonResponse({'success': False, 'error': 'No FC Character found'})

    if not check_token(fc_char):
        return JsonResponse({'success': False, 'error': 'FC Token Expired/Invalid'})

    try:
        headers = {'Authorization': f'Bearer {fc_char.access_token}'}
        resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            fleet.esi_fleet_id = data['fleet_id']
            fleet.save()
            
            return JsonResponse({'success': True, 'fleet_id': fleet.esi_fleet_id})
        elif resp.status_code == 404:
            return JsonResponse({'success': False, 'error': 'You are not in a fleet in-game. Please form fleet first.'})
        else:
            return JsonResponse({'success': False, 'error': f'ESI Error: {resp.status_code}'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(is_fleet_command)
@require_POST
def api_close_fleet(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    # Permission Check (Just in case, mostly handled by decorator)
    if not request.user.is_superuser and fleet.commander != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
    fleet.is_active = False
    fleet.end_time = timezone.now()
    fleet.save()
    
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_fleet_command)
def take_fleet_command(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    fleet.commander = request.user
    fleet.save()
    return redirect('fleet_dashboard', token=fleet.join_token)