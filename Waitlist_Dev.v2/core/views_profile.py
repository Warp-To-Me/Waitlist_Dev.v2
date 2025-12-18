import json
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    characters = request.user.characters.all()
    active_char_id = request.session.get('active_char_id')
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
    if active_char and not active_char.refresh_token: token_missing = True
    
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
        except Exception: pass

    totals = characters.aggregate(wallet_sum=Sum('wallet_balance'), lp_sum=Sum('concord_lp'), sp_sum=Sum('total_sp'))
    
    # Serialize Characters
    chars_data = []
    for c in characters:
        chars_data.append({
            'character_id': c.character_id,
            'character_name': c.character_name,
            'corporation_name': c.corporation_name,
            'is_main': c.is_main,
            'x_up_visible': c.x_up_visible
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

        if granted is not None:
             if 'esi-wallet.read_character_wallet.v1' not in granted:
                 wallet_val = None
             if 'esi-characters.read_loyalty.v1' not in granted:
                 lp_val = None
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
            'last_updated': active_char.last_updated
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
    if not character.refresh_token: return Response({'success': False, 'error': 'No refresh token'})
    
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