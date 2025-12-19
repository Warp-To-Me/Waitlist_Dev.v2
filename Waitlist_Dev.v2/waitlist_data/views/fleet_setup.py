import json
import requests
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import is_fleet_command, get_template_base, get_mgmt_context
from pilot_data.models import EveCharacter
from waitlist_data.models import Fleet, FleetStructureTemplate, StructureWing, StructureSquad
from esi_calls.fleet_service import sync_fleet_structure, update_fleet_settings, ESI_BASE
from esi.models import Token # Updated Import
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
    return render(request, 'management/fleet_setup.html', context)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_fleet_setup_init(request):
    if not is_fleet_command(request.user):
        return Response({'error': 'Permission Denied'}, status=403)

    # 1. Get FC Characters
    fc_chars = request.user.characters.all()
    chars_data = [{
        'character_id': c.character_id,
        'character_name': c.character_name,
        'is_main': c.is_main
    } for c in fc_chars]

    # 2. Get Saved Templates
    templates = FleetStructureTemplate.objects.filter(character__in=fc_chars).prefetch_related('wings', 'wings__squads')
    templates_data = []
    for t in templates:
        wings_data = [{'name': w.name, 'squads': [s.name for s in w.squads.all()]} for w in t.wings.all()]
        templates_data.append({
            'id': t.id,
            'name': t.name,
            'motd': t.default_motd,
            'wing_count': t.wings.count(),
            'wings': wings_data
        })

    return Response({
        'fc_chars': chars_data,
        'templates': templates_data
    })

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
            
    # Return full template object for Redux state update
    return JsonResponse({
        'success': True, 
        'template': {
            'id': template.id,
            'name': template.name,
            'motd': template.default_motd,
            'wing_count': len(wings_data),
            'wings': wings_data
        }
    })

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
    2. Checks ESI connection (Optional).
    3. Applies structure if valid (Optional).
    4. Sets MOTD if provided (Optional).
    """
    try:
        data = json.loads(request.body)
        fleet_name = data.get('fleet_name')
        char_id = data.get('character_id')
        structure = data.get('structure', []) 
        motd = data.get('motd', '') 
        is_offline = data.get('is_offline', False) # NEW: Offline Mode Flag
        
        if not fleet_name or not char_id:
            return JsonResponse({'success': False, 'error': 'Missing Name or FC Selection'})
            
        fc_char = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
        
        esi_fleet_id = None
        logs = []

        # 1. ESI Check (Skip if Offline)
        if not is_offline:
            # Token Refresh Logic
            esi_token = Token.objects.filter(character_id=fc_char.character_id).order_by('-created').first()
            if not esi_token:
                return JsonResponse({'success': False, 'error': 'FC Token Missing'})
            
            try:
                access_token = esi_token.valid_access_token()
                headers = {'Authorization': f'Bearer {access_token}'}
                
                resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    esi_fleet_id = resp.json()['fleet_id']
                elif resp.status_code == 404:
                    return JsonResponse({'success': False, 'error': 'You are not in a fleet in-game. Please form fleet first or use Offline Mode.'})
                else:
                    return JsonResponse({'success': False, 'error': f'ESI Error {resp.status_code}'})
                    
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Token/Network Error: {str(e)}'})
        else:
            logs.append("Fleet created in Offline Mode (No ESI Link).")

        # 2. Create Django Fleet
        fleet = Fleet.objects.create(
            name=fleet_name,
            commander=request.user,
            is_active=True,
            esi_fleet_id=esi_fleet_id,
            motd=motd
        )
        
        # 3. Apply Structure (Skip if Offline)
        if not is_offline and esi_fleet_id:
            success, struct_logs = sync_fleet_structure(esi_fleet_id, fc_char, structure)
            logs.extend(struct_logs)
            
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
            'redirect_url': f"/fleet/{fleet.join_token}",
            'logs': logs
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
