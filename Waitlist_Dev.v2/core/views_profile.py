import json
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Q
from django.conf import settings
from itertools import chain 
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Core Imports
from core.permissions import get_template_base, is_fleet_command, is_admin
from core.utils import get_character_data
from core.models import BanAuditLog

# Models & Services
from pilot_data.models import EveCharacter
from waitlist_data.models import FleetActivity
from waitlist_data.stats import calculate_pilot_stats
from scheduler.tasks import refresh_character_task
from esi.models import Token

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    # Trigger Update for Active Character (or all if simpler, but active is focus)
    active_char_id = request.session.get('active_char_id')
    if active_char_id:
        refresh_character_task.delay(active_char_id)
    
    characters = request.user.characters.all()
    if active_char_id: active_char = characters.filter(character_id=active_char_id).first()
    else:
        active_char = characters.filter(is_main=True).first()
        if not active_char and characters.exists(): active_char = characters.first()
        
    esi_data, grouped_skills = None, None
    if active_char:
        esi_data, grouped_skills = get_character_data(active_char)
    
    # --- Service Record Stats ---
    service_record = {}
    if active_char:
        service_record = calculate_pilot_stats(active_char)
    
        # 1. Fetch Fleet Logs
        fleet_logs = FleetActivity.objects.filter(character=active_char)\
            .select_related('fleet', 'actor').order_by('-timestamp')[:50]

        # 2. Fetch Ban Logs (Targeting the User account)
        ban_logs = BanAuditLog.objects.filter(target_user=active_char.user)\
            .select_related('actor').order_by('-timestamp')[:20]

        # 3. Merge & Sort
        # We need to serialize these for JSON response
        logs_data = []
        for log in fleet_logs:
            logs_data.append({
                'type': 'fleet',
                'timestamp': log.timestamp,
                'action': log.action,
                'details': log.details,
                'actor': log.actor.username if log.actor else 'System'
            })
        for log in ban_logs:
            logs_data.append({
                'type': 'ban',
                'timestamp': log.timestamp,
                'action': log.action,
                'details': log.details,
                'actor': log.actor.username if log.actor else 'System'
            })
            
        combined_logs = sorted(
            logs_data,
            key=lambda x: x['timestamp'],
            reverse=True
        )[:50]

        service_record['history_logs'] = combined_logs
        
        # hull_breakdown is a dict, need to listify
        if 'hull_breakdown' in service_record:
            service_record['hull_breakdown'] = sorted(
                [{'name': k, 'seconds': v} for k, v in service_record['hull_breakdown'].items()],
                key=lambda x: x['seconds'],
                reverse=True
            )
    
    token_missing = False
    if active_char:
        if not Token.objects.filter(character_id=active_char.character_id).exists():
            token_missing = True
    
    scopes_missing = False
    if active_char and is_fleet_command(request.user):
        token = Token.objects.filter(character_id=active_char.character_id).order_by('-created').first()
        if token:
            token_scopes = set(token.scopes.values_list('name', flat=True))
            required_fc = set(settings.EVE_SCOPES_FC.split())
            if not required_fc.issubset(token_scopes):
                scopes_missing = True
        else:
            scopes_missing = True

    # Calculate Aggregate Totals considering visibility flags
    totals_wallet = characters.filter(include_wallet_in_aggregate=True).aggregate(s=Sum('wallet_balance'))['s']
    totals_lp = characters.filter(include_lp_in_aggregate=True).aggregate(s=Sum('concord_lp'))['s']
    totals_sp = characters.filter(include_sp_in_aggregate=True).aggregate(s=Sum('total_sp'))['s']

    totals = {
        'wallet_sum': totals_wallet,
        'lp_sum': totals_lp,
        'sp_sum': totals_sp
    }
    
    # Serialize Characters
    chars_data = []
    for c in characters:
        # Determine missing scopes for UI disable logic
        c_granted = set(c.granted_scopes.split()) if c.granted_scopes else set()
        c_missing_wallet = 'esi-wallet.read_character_wallet.v1' not in c_granted
        c_missing_lp = 'esi-characters.read_loyalty.v1' not in c_granted
        c_missing_sp = 'esi-skills.read_skills.v1' not in c_granted

        chars_data.append({
            'character_id': c.character_id,
            'character_name': c.character_name,
            'corporation_name': c.corporation_name,
            'is_main': c.is_main,
            'x_up_visible': c.x_up_visible,
            # Aggregate Flags
            'include_wallet': c.include_wallet_in_aggregate,
            'include_lp': c.include_lp_in_aggregate,
            'include_sp': c.include_sp_in_aggregate,
            # Missing Scope Flags
            'missing_wallet_scope': c_missing_wallet,
            'missing_lp_scope': c_missing_lp,
            'missing_sp_scope': c_missing_sp
        })

    active_char_data = None
    if active_char:
        # Check scopes for data visibility
        granted = set(active_char.granted_scopes.split()) if active_char.granted_scopes else None
        
        wallet_val = active_char.wallet_balance
        lp_val = active_char.concord_lp
        ship_name_val = active_char.current_ship_name
        ship_type_val = getattr(active_char, 'ship_type_name', 'Unknown Hull')
        ship_id_val = active_char.current_ship_type_id

        # Flag missing scopes
        missing_wallet_scope = False
        missing_lp_scope = False
        missing_sp_scope = False

        if granted is not None:
             if 'esi-wallet.read_character_wallet.v1' not in granted:
                 wallet_val = None
                 missing_wallet_scope = True
             if 'esi-characters.read_loyalty.v1' not in granted:
                 lp_val = None
                 missing_lp_scope = True
             if 'esi-skills.read_skills.v1' not in granted:
                 missing_sp_scope = True
             if 'esi-location.read_ship_type.v1' not in granted:
                 ship_name_val = None
                 ship_type_val = None
                 ship_id_val = None

        active_char_data = {
            'character_id': active_char.character_id,
            'character_name': active_char.character_name,
            'corporation_name': active_char.corporation_name,
            'alliance_name': active_char.alliance_name,
            'is_main': active_char.is_main,
            'wallet_balance': wallet_val,
            'concord_lp': lp_val,
            'total_sp': active_char.total_sp,
            'current_ship_name': ship_name_val,
            'ship_type_name': ship_type_val,
            'current_ship_type_id': ship_id_val,
            'last_updated': active_char.last_updated,
            # Aggregate Flags
            'include_wallet': active_char.include_wallet_in_aggregate,
            'include_lp': active_char.include_lp_in_aggregate,
            'include_sp': active_char.include_sp_in_aggregate,
            # Missing Scope Flags (for UI enable/disable)
            'missing_wallet_scope': missing_wallet_scope,
            'missing_lp_scope': missing_lp_scope,
            'missing_sp_scope': missing_sp_scope
        }

    return Response({
        'active_char': active_char_data,
        'characters': chars_data,
        'esi': esi_data, # Assuming this is JSON serializable dict
        'grouped_skills': grouped_skills, # Assuming JSON serializable
        'service_record': service_record,
        'token_missing': token_missing,
        'scopes_missing': scopes_missing,
        'totals': {
            'wallet': totals['wallet_sum'] or 0,
            'lp': totals['lp_sum'] or 0,
            'sp': totals['sp_sum'] or 0
        },
        'is_admin_user': is_admin(request.user)
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_refresh_profile(request, char_id):
    """
    Triggers a background refresh task via Celery.
    """
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    if not Token.objects.filter(character_id=character.character_id).exists():
        return Response({'success': False, 'error': 'No refresh token'})
    
    refresh_character_task.delay(character.character_id)
    return Response({'success': True, 'status': 'queued'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_pilot_status(request, char_id):
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    return Response({
        'id': character.character_id,
        'last_updated': character.last_updated.isoformat() if character.last_updated else None
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def switch_character(request, char_id):
    # This was a redirect, but for SPA we just set session and return OK
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    request.session['active_char_id'] = character.character_id
    return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def make_main(request, char_id):
    new_main = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    request.user.characters.update(is_main=False)
    new_main.is_main = True
    new_main.save()
    request.session['active_char_id'] = new_main.character_id
    return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_toggle_xup_visibility(request):
    char_id = request.data.get('character_id')
    if not char_id: return Response({'success': False, 'error': 'Character ID required'}, status=400)

    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    character.x_up_visible = not character.x_up_visible
    character.save(update_fields=['x_up_visible'])
    
    return Response({
        'success': True, 
        'character_id': character.character_id, 
        'new_state': character.x_up_visible
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_toggle_aggregate_setting(request):
    """
    Toggles the inclusion of specific metrics (wallet, lp, sp) in the account aggregate totals.
    Payload: { character_id: int, setting: 'wallet' | 'lp' | 'sp', value: boolean }
    """
    char_id = request.data.get('character_id')
    setting = request.data.get('setting')
    value = request.data.get('value')

    if not char_id or not setting:
        return Response({'success': False, 'error': 'Missing parameters'}, status=400)
    
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)

    if setting == 'wallet':
        character.include_wallet_in_aggregate = value
        character.save(update_fields=['include_wallet_in_aggregate'])
    elif setting == 'lp':
        character.include_lp_in_aggregate = value
        character.save(update_fields=['include_lp_in_aggregate'])
    elif setting == 'sp':
        character.include_sp_in_aggregate = value
        character.save(update_fields=['include_sp_in_aggregate'])
    else:
        return Response({'success': False, 'error': 'Invalid setting type'}, status=400)

    return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_bulk_toggle_aggregate(request):
    """
    Toggles the inclusion of specific metrics for ALL characters of the user.
    Payload: { setting: 'wallet' | 'lp' | 'sp', value: boolean }
    """
    setting = request.data.get('setting')
    value = request.data.get('value')

    if not setting:
        return Response({'success': False, 'error': 'Missing parameters'}, status=400)
    
    characters = request.user.characters.all()

    if setting == 'wallet':
        characters.update(include_wallet_in_aggregate=value)
    elif setting == 'lp':
        characters.update(include_lp_in_aggregate=value)
    elif setting == 'sp':
        characters.update(include_sp_in_aggregate=value)
    else:
        return Response({'success': False, 'error': 'Invalid setting type'}, status=400)

    return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_unlink_character(request):
    """
    Removes a character from the user account. Admin only.
    """
    if not is_admin(request.user):
        return Response({'success': False, 'error': 'Permission denied'}, status=403)

    char_id = request.data.get('character_id')
    if not char_id:
        return Response({'success': False, 'error': 'Character ID required'}, status=400)

    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    
    # Prevent removing main character if it's the only one, or force new main assignment?
    # Logic: Delete the character. If it was main, user has no main until they switch.
    # Frontend handles switching active char if current is deleted.
    
    character.delete()
    return Response({'success': True, 'character_id': char_id})