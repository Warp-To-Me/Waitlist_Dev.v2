from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.permissions import is_fleet_command, can_view_fleet_overview
from core.eft_parser import EFTParser
from waitlist_data.models import Fleet, WaitlistEntry, FleetActivity
from pilot_data.models import EveCharacter
from waitlist_data.fitting_service import SmartFitMatcher
from esi_calls.fleet_service import invite_to_fleet
from .helpers import _log_fleet_action, broadcast_update, _build_fit_analysis_response, trigger_sibling_updates
from core.decorators import check_ban_status

@login_required
@check_ban_status
@require_POST
def x_up_submit(request, token):
    fleet = get_object_or_404(Fleet, join_token=token, is_active=True)
    
    char_ids = request.POST.getlist('character_id')
    raw_eft = request.POST.get('eft_paste', '').strip()
    
    if not char_ids: return JsonResponse({'success': False, 'error': 'No pilots selected.'})
    if not raw_eft: return JsonResponse({'success': False, 'error': 'No fitting provided.'})

    characters = EveCharacter.objects.filter(character_id__in=char_ids, user=request.user)
    if not characters.exists(): return JsonResponse({'success': False, 'error': 'Invalid characters.'})

    fit_blocks = []
    current_block = []
    lines = raw_eft.splitlines()
    for line in lines:
        sline = line.strip()
        is_header = sline.startswith('[') and sline.endswith(']') and ',' in sline
        if is_header:
            if current_block: fit_blocks.append("\n".join(current_block))
            current_block = []
        if sline or current_block: current_block.append(line)
    if current_block: fit_blocks.append("\n".join(current_block))

    if not fit_blocks: return JsonResponse({'success': False, 'error': 'Could not parse fits.'})

    processed_count = 0
    errors = []

    for char in characters:
        for fit_text in fit_blocks:
            parser = EFTParser(fit_text)
            if not parser.parse(): continue
            
            hull_obj = parser.hull_obj
            
            matcher = SmartFitMatcher(parser)
            matched_fit, analysis = matcher.find_best_match()
            
            fit_name_for_log = matched_fit.name if matched_fit else "Custom Fit"

            if WaitlistEntry.objects.filter(
                fleet=fleet, 
                character=char, 
                raw_eft=fit_text,
                status__in=['pending', 'approved', 'invited']
            ).exists():
                continue

            entry = WaitlistEntry.objects.create(
                fleet=fleet, 
                character=char, 
                fit=matched_fit, 
                hull=hull_obj, 
                raw_eft=fit_text, 
                status='pending'
            )
            
            _log_fleet_action(
                fleet, 
                char, 
                'x_up', 
                actor=request.user, 
                ship_type=hull_obj, 
                details=f"Fit: {fit_name_for_log}", 
                eft_text=fit_text
            )
            
            # Re-fetch for full depth
            entry = WaitlistEntry.objects.select_related('character__user', 'fit', 'hull', 'fit__ship_type', 'fit__category').get(id=entry.id)

            # 1. Update this card
            broadcast_update(fleet.id, 'add', entry, target_col='pending')
            
            # 2. Update siblings (add new dot to them)
            trigger_sibling_updates(fleet.id, char.character_id, exclude_entry_id=entry.id)
            
            processed_count += 1

    if processed_count == 0 and errors: return JsonResponse({'success': False, 'error': " | ".join(errors[:3])})
    
    return JsonResponse({'success': True, 'message': f"Submitted {processed_count} entries."})

@login_required
@require_POST
def update_fit(request, entry_id):
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    if entry.character.user != request.user: return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    raw_eft = request.POST.get('eft_paste', '')
    if not raw_eft: return JsonResponse({'success': False, 'error': 'Fit required.'})

    parser = EFTParser(raw_eft)
    if not parser.parse(): return JsonResponse({'success': False, 'error': f"Invalid Fit: {parser.error}"})

    matcher = SmartFitMatcher(parser)
    matched_fit, analysis = matcher.find_best_match()

    old_fit_name = entry.fit.name if entry.fit else "Custom Fit"
    new_fit_name = matched_fit.name if matched_fit else "Custom Fit"

    entry.fit = matched_fit
    entry.hull = parser.hull_obj
    entry.raw_eft = raw_eft
    entry.status = 'pending' 
    entry.save()

    _log_fleet_action(entry.fleet, entry.character, 'fit_update', actor=request.user, ship_type=parser.hull_obj, details=f"{old_fit_name} -> {new_fit_name}", eft_text=raw_eft)

    entry = WaitlistEntry.objects.select_related('character__user', 'fit', 'hull', 'fit__ship_type', 'fit__category').get(id=entry.id)

    # 1. Update this card
    broadcast_update(entry.fleet.id, 'move', entry, target_col='pending')
    
    # 2. Update siblings (category might have changed, updating indicators)
    trigger_sibling_updates(entry.fleet.id, entry.character.character_id, exclude_entry_id=entry.id)
    
    return JsonResponse({'success': True, 'message': f"Updated to: {new_fit_name}"})

@login_required
@require_POST
def leave_fleet(request, entry_id):
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    if entry.character.user != request.user: return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    
    fleet_id = entry.fleet.id
    char_id = entry.character.character_id
    
    _log_fleet_action(entry.fleet, entry.character, 'left_waitlist', actor=request.user, details="User initiated leave")
    
    entry.delete()
    
    # 1. Remove this card
    broadcast_update(fleet_id, 'remove', entry)
    
    # 2. Update siblings (remove dot representing this entry)
    trigger_sibling_updates(fleet_id, char_id)
    
    return JsonResponse({'success': True})

@login_required
def api_entry_details(request, entry_id):
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    is_owner = entry.character.user == request.user
    can_inspect = can_view_fleet_overview(request.user)
    
    if not is_owner and not can_inspect: return HttpResponse("Unauthorized", status=403)

    data = _build_fit_analysis_response(entry.raw_eft, entry.fit, entry.hull, entry.character, can_inspect)
    data['status'] = entry.status
    data['id'] = entry.id
    
    return JsonResponse(data)

@login_required
def api_history_fit_details(request, log_id):
    log = get_object_or_404(FleetActivity, id=log_id)
    is_owner = log.character.user == request.user
    if not is_fleet_command(request.user) and not is_owner: return HttpResponse("Unauthorized", status=403)
    if not log.fit_eft: return JsonResponse({'error': 'No fit data.'}, status=404)

    parser = EFTParser(log.fit_eft)
    parser.parse()
    matcher = SmartFitMatcher(parser)
    matched_fit, _ = matcher.find_best_match()
    
    data = _build_fit_analysis_response(log.fit_eft, matched_fit, parser.hull_obj, log.character, True)
    return JsonResponse(data)

@login_required
def fc_action(request, entry_id, action):
    if not is_fleet_command(request.user): return HttpResponse("Unauthorized", status=403)
    
    # Pre-fetch relations needed for broadcasting to avoid N+1 issues in broadcast_update
    # This speeds up the request significantly
    entry = get_object_or_404(
        WaitlistEntry.objects.select_related(
            'fleet', 
            'character__user', 
            'character__stats',  # New stats relation
            'fit__ship_type', 
            'fit__category',
            'hull'
        ), 
        id=entry_id
    )
    fleet = entry.fleet
    
    if action == 'approve':
        entry.status = 'approved'; entry.approved_at = timezone.now(); entry.save()
        hull_for_log = entry.hull if entry.hull else entry.fit.ship_type if entry.fit else None
        _log_fleet_action(fleet, entry.character, 'approved', actor=request.user, ship_type=hull_for_log)
        
        # Determine column manually or let helper do it
        # Since we just updated status to approved, helper's 'pending' check will fail and it will check fit category
        broadcast_update(fleet.id, 'move', entry)
        
        # Approval moves card out of pending -> update sibling dots
        trigger_sibling_updates(fleet.id, entry.character.character_id, exclude_entry_id=entry.id)
        
    elif action == 'deny':
        hull_for_log = entry.hull if entry.hull else entry.fit.ship_type if entry.fit else None
        _log_fleet_action(fleet, entry.character, 'denied', actor=request.user, ship_type=hull_for_log, details="Manual FC Rejection")
        entry.status = 'rejected'; entry.save()
        
        # Remove card
        broadcast_update(fleet.id, 'remove', entry)
        
        # Update siblings (remove dot)
        trigger_sibling_updates(fleet.id, entry.character.character_id, exclude_entry_id=entry.id)
        
    elif action == 'invite':
        fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
        if not fleet.esi_fleet_id: return JsonResponse({'success': False, 'error': 'No ESI Fleet linked.'})
        success, msg = invite_to_fleet(fleet.esi_fleet_id, fc_char, entry.character.character_id)
        if success:
            entry.status = 'invited'; entry.invited_at = timezone.now(); entry.save()
            hull_for_log = entry.hull if entry.hull else entry.fit.ship_type if entry.fit else None
            _log_fleet_action(
                fleet, 
                entry.character, 
                'invited', 
                actor=request.user, 
                ship_type=hull_for_log, 
                details="ESI Invite Sent",
                eft_text=entry.raw_eft
            )
            
            broadcast_update(fleet.id, 'move', entry)
            # Invite doesn't change column, but maybe status change affects something? Safe to trigger.
            trigger_sibling_updates(fleet.id, entry.character.character_id, exclude_entry_id=entry.id)
            
            return JsonResponse({'success': True})
        else: return JsonResponse({'success': False, 'error': f'Invite Failed: {msg}'})
    return JsonResponse({'success': True})