import json
import requests
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.permissions import is_fleet_command, get_template_base, get_mgmt_context
from pilot_data.models import EveCharacter
from waitlist_data.models import Fleet, FleetStructureTemplate, StructureWing, StructureSquad
from esi_calls.fleet_service import sync_fleet_structure, update_fleet_settings, ESI_BASE
from esi_calls.token_manager import check_token
from .helpers import _log_fleet_action

@login_required
@user_passes_test(is_fleet_command)
def fleet_setup(request):
    """
    Renders the Fleet Setup Wizard.
    """
    # 1. Get FC Characters
    fc_chars = request.user.characters.all()
    
    # 2. Get Saved Templates
    templates = FleetStructureTemplate.objects.filter(character__in=fc_chars).prefetch_related('wings', 'wings__squads')
    
    context = {
        'fc_chars': fc_chars,
        'templates': templates,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'waitlist/fleet_setup.html', context)

@login_required
@user_passes_test(is_fleet_command)
@require_POST
def api_save_structure_template(request):
    try:
        data = json.loads(request.body)
        char_id = data.get('character_id')
        name = data.get('template_name', 'My Template')
        wings_data = data.get('structure', [])
        motd = data.get('motd', '') 
    except json.JSONDecodeError: return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    
    # Create Template
    template = FleetStructureTemplate.objects.create(
        character=character,
        name=name,
        default_motd=motd
    )
    
    # Create Structure
    for i, w_data in enumerate(wings_data):
        wing = StructureWing.objects.create(
            template=template,
            name=w_data['name'],
            order=i
        )
        for j, s_name in enumerate(w_data.get('squads', [])):
            StructureSquad.objects.create(
                wing=wing,
                name=s_name,
                order=j
            )
            
    return JsonResponse({'success': True, 'template_id': template.id})

@login_required
@user_passes_test(is_fleet_command)
@require_POST
def api_delete_structure_template(request):
    try:
        data = json.loads(request.body)
        template_id = data.get('template_id')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    if not template_id:
        return JsonResponse({'success': False, 'error': 'Template ID required'})

    # Verify ownership (Template -> Character -> User)
    template = get_object_or_404(FleetStructureTemplate, id=template_id)
    if template.character.user != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied: Not your template'}, status=403)

    template.delete()
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_fleet_command)
@require_POST
def api_create_fleet_with_structure(request):
    """
    1. Creates Django Fleet.
    2. Checks ESI connection.
    3. Applies structure if valid.
    4. Sets MOTD if provided.
    """
    try:
        data = json.loads(request.body)
        fleet_name = data.get('fleet_name')
        char_id = data.get('character_id')
        structure = data.get('structure', []) 
        motd = data.get('motd', '') 
        
        if not fleet_name or not char_id:
            return JsonResponse({'success': False, 'error': 'Missing Name or FC Selection'})
            
        fc_char = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
        
        # 1. ESI Check
        headers = {'Authorization': f'Bearer {fc_char.access_token}'}
        esi_fleet_id = None
        try:
            if check_token(fc_char):
                resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers, timeout=5)
                if resp.status_code == 200:
                    esi_fleet_id = resp.json()['fleet_id']
                elif resp.status_code == 404:
                    return JsonResponse({'success': False, 'error': 'You are not in a fleet in-game. Please form fleet first.'})
                else:
                    return JsonResponse({'success': False, 'error': f'ESI Error {resp.status_code}'})
            else:
                return JsonResponse({'success': False, 'error': 'Token Expired'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

        # 2. Create Django Fleet
        fleet = Fleet.objects.create(
            name=fleet_name,
            commander=request.user,
            is_active=True,
            esi_fleet_id=esi_fleet_id,
            motd=motd
        )
        
        # 3. Apply Structure
        success, logs = sync_fleet_structure(esi_fleet_id, fc_char, structure)
        
        # 4. Apply MOTD
        if motd:
            success_motd, msg_motd = update_fleet_settings(esi_fleet_id, fc_char, motd=motd)
            logs.append(f"MOTD Update: {msg_motd}")

        # Log results
        if logs:
            for log in logs:
                _log_fleet_action(fleet, fc_char, 'esi_join', details=log)

        return JsonResponse({
            'success': True, 
            'redirect_url': f"/fleet/{fleet.join_token}/dashboard/",
            'logs': logs
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})