import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core.permissions import is_fleet_command, get_template_base, get_mgmt_context
from waitlist_data.models import Fleet, FleetStructureTemplate
from esi_calls.fleet_service import get_fleet_composition, sync_fleet_structure, update_fleet_settings, cleanup_fleet_cache, ESI_BASE
from esi.models import Token # Updated Import

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
    if fleet.esi_fleet_id and Token.objects.filter(character_id=fc_char.character_id).exists():
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

    # NEW: Fetch Saved Templates for the Sidebar
    fc_chars = request.user.characters.all()
    templates = FleetStructureTemplate.objects.filter(character__in=fc_chars).prefetch_related('wings', 'wings__squads')

    context = {
        'fleet': fleet,
        'fc_char': fc_char,
        'initial_structure': initial_structure,
        'templates': templates,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/fleet_settings.html', context)

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

    # Token Logic
    esi_token = Token.objects.filter(character_id=fc_char.character_id).order_by('-created').first()
    if not esi_token:
        return JsonResponse({'success': False, 'error': 'FC Token Expired/Invalid'})

    try:
        access_token = esi_token.valid_access_token()
        headers = {'Authorization': f'Bearer {access_token}'}
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

    # CLEANUP CACHE
    try:
        for char in request.user.characters.all():
            cleanup_fleet_cache(char, fleet.esi_fleet_id)
    except Exception:
        pass

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

@login_required
@user_passes_test(is_fleet_command)
@require_POST
def api_take_over_fleet(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    # CLEANUP OLD COMMANDER CACHE
    try:
        old_commander = fleet.commander
        if old_commander:
            for char in old_commander.characters.all():
                cleanup_fleet_cache(char, fleet.esi_fleet_id)
    except Exception:
        pass

    # Update Commander
    fleet.commander = request.user
    
    # Find new FC's active character for linking
    fc_char = request.user.characters.filter(is_main=True).first() or request.user.characters.first()
    
    linked_id = None
    error_msg = None
    
    if fc_char:
        esi_token = Token.objects.filter(character_id=fc_char.character_id).order_by('-created').first()
        if esi_token:
            try:
                access_token = esi_token.valid_access_token()
                headers = {'Authorization': f'Bearer {access_token}'}
                resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    data = resp.json()
                    linked_id = data['fleet_id']
                    fleet.esi_fleet_id = linked_id
                elif resp.status_code == 404:
                    error_msg = "You are now FC, but you are not in a fleet in-game. Please form fleet and link manually."
                    # Clear esi_fleet_id so we don't try to use the old one
                    fleet.esi_fleet_id = None
                else:
                    error_msg = f"ESI Error {resp.status_code} during link attempt."
                    fleet.esi_fleet_id = None
            except Exception as e:
                error_msg = f"Link failed: {str(e)}"
                fleet.esi_fleet_id = None
        else:
            error_msg = "Your character has no valid token."
            fleet.esi_fleet_id = None
    else:
        error_msg = "You have no valid character to link fleet with."
        fleet.esi_fleet_id = None

    fleet.save()
    
    # Broadcast Update
    channel_layer = get_channel_layer()
    group_name = f'fleet_{fleet.id}'
    
    fc_name = fc_char.character_name if fc_char else request.user.username
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'fleet_update',
            'action': 'fleet_meta', # New action type for meta updates
            'data': {
                'fleet': {
                    'id': fleet.id,
                    'token': str(fleet.join_token),
                    'name': fleet.name,
                    'description': fleet.motd,
                    'is_active': fleet.is_active,
                    'commander_name': fc_name,
                    'esi_fleet_id': fleet.esi_fleet_id
                }
            }
        }
    )
    
    return JsonResponse({
        'success': True, 
        'message': error_msg or "Fleet command assumed and linked successfully.",
        'warning': error_msg
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_fleet_settings(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    if not is_fleet_command(request.user):
        return Response({'error': 'Permission Denied'}, status=403)
        
    fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
    
    # Structure Logic (similar to HTML view)
    initial_structure = []
    if fleet.esi_fleet_id and fc_char and Token.objects.filter(character_id=fc_char.character_id).exists():
        comp, err = get_fleet_composition(fleet.esi_fleet_id, fc_char)
        if comp:
            raw_wings = comp.get('wings', [])
            raw_wings.sort(key=lambda x: x['id'])
            for w in raw_wings:
                squads = [s['name'] for s in sorted(w.get('squads', []), key=lambda x: x['id'])]
                initial_structure.append({
                    'name': w['name'],
                    'squads': squads
                })

    # Fetch Templates
    fc_chars = request.user.characters.all()
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
        'fleet': {
            'id': fleet.id,
            'name': fleet.name,
            'motd': fleet.motd,
            'status': fleet.status,
            'esi_fleet_id': fleet.esi_fleet_id,
            'commander_id': fc_char.character_id if fc_char else None,
            'join_token': str(fleet.join_token)
        },
        'structure': initial_structure,
        'templates': templates_data
    })
