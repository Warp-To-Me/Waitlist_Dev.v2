from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import requests 
from collections import defaultdict # Added for aggregation

# Core Imports
from core.utils import get_role_priority, ROLE_HIERARCHY
from core.eft_parser import EFTParser
from core.models import Capability 

# Model Imports
from pilot_data.models import EveCharacter, TypeEffect, ItemGroup
from .models import DoctrineCategory, DoctrineFit, FitModule, DoctrineTag, Fleet, WaitlistEntry

# ESI Services
from esi_calls.fleet_service import get_fleet_composition, process_fleet_data, invite_to_fleet, ESI_BASE
from esi_calls.token_manager import check_token

# NEW IMPORT:
from .fitting_service import SmartFitMatcher, FitComparator, ComparisonStatus

# --- HELPERS ---

def get_template_base(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return 'base_content.html'
    return 'base.html'

def is_fleet_command(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='access_fleet_command').exists()

def is_resident(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='view_fleet_overview').exists()

def is_admin(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='access_admin').exists()

def can_manage_doctrines(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='manage_doctrines').exists()

def get_mgmt_context(user):
    if user.is_superuser:
        perms = set(Capability.objects.values_list('slug', flat=True))
    else:
        perms = set(Capability.objects.filter(groups__user=user).values_list('slug', flat=True).distinct())

    return {
        'user_perms': perms,
        'can_view_fleets': 'access_fleet_command' in perms,
        'can_view_admin': 'access_admin' in perms,
        'is_fc': 'access_fleet_command' in perms
    }

def _process_category_icons(category):
    seen_ids = set()
    unique_ships = []
    for fit in category.fits.all():
        if fit.ship_type.type_id not in seen_ids:
            seen_ids.add(fit.ship_type.type_id)
            unique_ships.append(fit.ship_type)
    for sub in category.subcategories.all():
        sub_ships = _process_category_icons(sub) 
        for ship in sub_ships:
            if ship.type_id not in seen_ids:
                seen_ids.add(ship.type_id)
                unique_ships.append(ship)
    category.unique_ship_icons = unique_ships
    return unique_ships

def _determine_slot(item_type):
    """
    Uses TypeEffect (Dogma Effects) to determine if an item is High/Mid/Low/Rig.
    Falls back to Category ID for Subsystems/Drones.
    """
    effects = set(TypeEffect.objects.filter(item=item_type).values_list('effect_id', flat=True))
    
    # 12 = hiPower, 13 = medPower, 11 = loPower, 2663 = rigSlot
    if 12 in effects: return 'high'
    if 13 in effects: return 'mid'
    if 11 in effects: return 'low'
    if 2663 in effects: return 'rig'
    
    try:
        # If no effect found, check Category via Group
        if item_type.group:
            cat_id = item_type.group.category_id
            if cat_id == 32: return 'subsystem'
            if cat_id == 18 or cat_id == 87: return 'drone'
            if cat_id == 8: return 'cargo' # Charges
    except Exception:
        pass
        
    return 'cargo'

# --- WEBSOCKET BROADCASTER ---

def broadcast_update(fleet_id, action, entry, target_col=None):
    channel_layer = get_channel_layer()
    group_name = f'fleet_{fleet_id}'
    
    payload = {
        'type': 'fleet_update',
        'action': action,
        'entry_id': entry.id
    }

    if action in ['add', 'move']:
        context = {'entry': entry, 'is_fc': True}
        html = render_to_string('waitlist/entry_card.html', context)
        payload['html'] = html
        payload['target_col'] = target_col

    async_to_sync(channel_layer.group_send)(group_name, payload)


# --- PUBLIC DOCTRINE VIEWS ---

def doctrine_list(request):
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'fits__ship_type', 'fits__tags',
        'subcategories__fits__ship_type', 'subcategories__fits__tags',
        'subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__subcategories__fits__tags'
    )
    for cat in categories:
        _process_category_icons(cat)
    context = {
        'categories': categories,
        'base_template': get_template_base(request)
    }
    return render(request, 'doctrines/public_index.html', context)

def doctrine_detail_api(request, fit_id):
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    hull = fit.ship_type
    raw_modules = fit.modules.select_related('item_type').prefetch_related('item_type__attributes').all()
    
    # AGGREGATION LOGIC
    # Map: (slot, type_id) -> {data}
    aggregated = {}
    
    for mod in raw_modules:
        key = (mod.slot, mod.item_type.type_id)
        if key not in aggregated:
            aggregated[key] = {
                'name': mod.item_type.type_name,
                'id': mod.item_type.type_id,
                'quantity': 0,
                'slot': mod.slot
            }
        aggregated[key]['quantity'] += mod.quantity

    modules_by_slot = { 'high': [], 'mid': [], 'low': [], 'rig': [], 'subsystem': [], 'drone': [], 'cargo': [] }
    
    for data in aggregated.values():
        if data['slot'] in modules_by_slot:
            modules_by_slot[data['slot']].append(data)

    high_total = int(hull.high_slots)
    mid_total = int(hull.mid_slots)
    low_total = int(hull.low_slots)
    rig_total = int(hull.rig_slots)
    
    # Handle T3C Subsystem Slots affecting Hardpoints
    if hull.group_id == 963:
        for mod in raw_modules:
            attrs = {a.attribute_id: a.value for a in mod.item_type.attributes.all()}
            if 14 in attrs: high_total += int(attrs[14])
            if 13 in attrs: mid_total += int(attrs[13])
            if 12 in attrs: low_total += int(attrs[12])

    slot_config = [
        ('High Slots', 'high', high_total),
        ('Mid Slots', 'mid', mid_total),
        ('Low Slots', 'low', low_total),
        ('Rigs', 'rig', rig_total),
        ('Subsystems', 'subsystem', 5 if hull.group_id == 963 else 0),
        ('Drone Bay', 'drone', 0),
        ('Cargo Hold', 'cargo', 0),
    ]

    slot_groups = []
    for label, key, total_attr in slot_config:
        mods = modules_by_slot.get(key, [])
        # Used count is sum of quantities, not just list length
        used_count = sum(m['quantity'] for m in mods)
        
        if total_attr < used_count: total_attr = used_count
        is_hardpoint = key in ['high', 'mid', 'low', 'rig', 'subsystem']
        empties_count = max(0, total_attr - used_count) if is_hardpoint else 0
        
        if total_attr > 0 or used_count > 0:
            slot_groups.append({
                'name': label, 'key': key, 'total': total_attr if is_hardpoint else None,
                'used': used_count if is_hardpoint else None, 'modules': mods,
                'empties_count': empties_count, 'is_hardpoint': is_hardpoint
            })

    data = {
        'id': fit.id, 'name': fit.name, 'hull': hull.type_name,
        'hull_id': hull.type_id, 'description': fit.description,
        'eft_format': fit.eft_format, 'slots': slot_groups
    }
    return JsonResponse(data)


# --- FLEET / WAITLIST VIEWS ---

@login_required
def fleet_dashboard(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    fc_name = EveCharacter.objects.filter(user=fleet.commander, is_main=True).values_list('character_name', flat=True).first()
    if not fc_name:
        fc_name = EveCharacter.objects.filter(user=fleet.commander).values_list('character_name', flat=True).first()
    if not fc_name:
        fc_name = fleet.commander.username

    entries = WaitlistEntry.objects.filter(fleet=fleet).exclude(status__in=['rejected', 'left']).select_related(
        'character', 'fit', 'fit__ship_type', 'fit__category'
    ).order_by('created_at')

    columns = {'pending': [], 'logi': [], 'dps': [], 'sniper': [], 'other': []}
    
    for entry in entries:
        if entry.status == 'pending':
            columns['pending'].append(entry)
        else:
            tags = [t.name.lower() for t in entry.fit.tags.all()]
            cat_name = entry.fit.category.name.lower()
            if 'logi' in tags or 'logistics' in cat_name: columns['logi'].append(entry)
            elif 'sniper' in tags: columns['sniper'].append(entry)
            elif 'dps' in tags or 'brawl' in tags: columns['dps'].append(entry)
            else: columns['other'].append(entry)

    user_chars = request.user.characters.all()
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related('subcategories__fits')
    can_view_overview = is_resident(request.user)

    context = {
        'fleet': fleet,
        'fc_name': fc_name,
        'columns': columns,
        'user_chars': user_chars,
        'categories': categories,
        'is_fc': is_fleet_command(request.user),
        'is_commander': request.user == fleet.commander,
        'can_view_overview': can_view_overview,
        'base_template': get_template_base(request)
    }
    return render(request, 'waitlist/dashboard.html', context)


@login_required
@require_POST
def x_up_submit(request, token):
    """
    Handles pilot submitting a fit. URL uses Token.
    UPDATED: Uses SmartFitMatcher.
    """
    fleet = get_object_or_404(Fleet, join_token=token, is_active=True)
    char_id = request.POST.get('character_id')
    raw_eft = request.POST.get('eft_paste', '')
    
    if not char_id or not raw_eft:
        return JsonResponse({'success': False, 'error': 'Missing character or fitting.'})

    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    
    parser = EFTParser(raw_eft)
    if not parser.parse():
        return JsonResponse({'success': False, 'error': f"Invalid Fit Format: {parser.error}"})
    
    # --- NEW: Smart Matching Logic ---
    matcher = SmartFitMatcher(parser)
    matched_fit, analysis = matcher.find_best_match()
    
    # Fallback to simple ship matching if no doctrine fits found, or reject?
    if not matched_fit:
        return JsonResponse({'success': False, 'error': f"No doctrine found for ship '{parser.hull_obj.type_name}'."})

    if WaitlistEntry.objects.filter(fleet=fleet, character=character, status__in=['pending', 'approved', 'invited']).exists():
        return JsonResponse({'success': False, 'error': 'You are already in the waitlist.'})

    entry = WaitlistEntry.objects.create(
        fleet=fleet, character=character, fit=matched_fit, raw_eft=raw_eft, status='pending'
    )
    
    broadcast_update(fleet.id, 'add', entry, target_col='pending')
    
    # Add feedback about the match
    # Example: "Matches 'Paladin - Sniper' (Downgrades detected)"
    warnings = [i for i in analysis if i['status'] == ComparisonStatus.DOWNGRADE] if analysis else []
    msg = f"Matched: {matched_fit.name}"
    if warnings:
        msg += f" ({len(warnings)} downgrades)"
        
    return JsonResponse({'success': True, 'message': msg})

@login_required
@require_POST
def update_fit(request, entry_id):
    """
    Allows a user to update their existing fit.
    """
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    if entry.character.user != request.user:
        return JsonResponse({'success': False, 'error': 'Not your entry.'}, status=403)

    raw_eft = request.POST.get('eft_paste', '')
    if not raw_eft:
        return JsonResponse({'success': False, 'error': 'Fit required.'})

    parser = EFTParser(raw_eft)
    if not parser.parse():
        return JsonResponse({'success': False, 'error': f"Invalid Fit: {parser.error}"})

    matcher = SmartFitMatcher(parser)
    matched_fit, analysis = matcher.find_best_match()

    if not matched_fit:
        return JsonResponse({'success': False, 'error': f"No doctrine found for ship '{parser.hull_obj.type_name}'."})

    # Update Entry
    entry.fit = matched_fit
    entry.raw_eft = raw_eft
    # IMPORTANT: Do we reset status? 
    # Usually updating a fit resets approval unless configured otherwise.
    # For now, let's keep it 'pending' if it was pending, or reset to 'pending' if approved?
    # To be safe and force re-check, we reset to 'pending'.
    entry.status = 'pending' 
    entry.save()

    broadcast_update(entry.fleet.id, 'move', entry, target_col='pending')
    
    warnings = [i for i in analysis if i['status'] == ComparisonStatus.DOWNGRADE] if analysis else []
    msg = f"Updated to: {matched_fit.name}"
    if warnings:
        msg += f" ({len(warnings)} downgrades)"

    return JsonResponse({'success': True, 'message': msg})

@login_required
@require_POST
def leave_fleet(request, entry_id):
    """
    Allows a user to remove themselves from the waitlist.
    """
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    if entry.character.user != request.user:
        return JsonResponse({'success': False, 'error': 'Not your entry.'}, status=403)
    
    fleet_id = entry.fleet.id
    entry.delete()
    
    broadcast_update(fleet_id, 'remove', entry)
    return JsonResponse({'success': True})

@login_required
def api_entry_details(request, entry_id):
    """
    Returns detailed fit analysis for the modal.
    UPDATED: Now includes comparison status per slot and AGGREGATES items.
    """
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    is_owner = entry.character.user == request.user
    can_inspect = is_resident(request.user)
    if not is_owner and not can_inspect:
        return HttpResponse("Unauthorized", status=403)

    parser = EFTParser(entry.raw_eft)
    parser.parse() 
    hull = entry.fit.ship_type
    
    matcher = SmartFitMatcher(parser)
    _, analysis = matcher._score_fit(entry.fit)
    
    # --- AGGREGATION LOGIC ---
    # We group by (slot, pilot_item_id, doctrine_item_id, status)
    aggregated = {}
    
    for item in analysis:
        # item: { slot, doctrine_item, pilot_item, status, diffs }
        slot_key = item['slot']
        status = item['status']
        
        # ID Handling (Handle None for missing/extra)
        p_id = item['pilot_item'].type_id if item['pilot_item'] else 0
        d_id = item['doctrine_item'].type_id if item['doctrine_item'] else 0
        
        # Names
        p_name = item['pilot_item'].type_name if item['pilot_item'] else None
        d_name = item['doctrine_item'].type_name if item['doctrine_item'] else None
        
        # Unique Key for Grouping
        group_key = (slot_key, p_id, d_id, status)
        
        if group_key not in aggregated:
            aggregated[group_key] = {
                'name': p_name or d_name or "Empty",
                'id': p_id or d_id,
                'quantity': 0,
                'status': status,
                'diffs': item['diffs'], # Assuming diffs are identical for same items
                'doctrine_name': d_name,
                'slot': slot_key
            }
        
        aggregated[group_key]['quantity'] += 1

    # Convert to standard map structure
    slots_map = { 'high': [], 'mid': [], 'low': [], 'rig': [], 'subsystem': [], 'drone': [], 'cargo': [] }
    
    for data in aggregated.values():
        s = data['slot']
        if s not in slots_map: s = 'cargo'
        slots_map[s].append(data)

    # Calculate Totals
    high_total = int(hull.high_slots)
    mid_total = int(hull.mid_slots)
    low_total = int(hull.low_slots)
    rig_total = int(hull.rig_slots)
    
    # Handle T3Cs
    if hull.group_id == 963:
        for item in parser.items:
            attrs = {a.attribute_id: a.value for a in item['obj'].attributes.all()}
            if 14 in attrs: high_total += int(attrs[14])
            if 13 in attrs: mid_total += int(attrs[13])
            if 12 in attrs: low_total += int(attrs[12])

    slot_config = [
        ('High Slots', 'high', high_total), ('Mid Slots', 'mid', mid_total),
        ('Low Slots', 'low', low_total), ('Rigs', 'rig', rig_total),
        ('Subsystems', 'subsystem', 5 if hull.group_id == 963 else 0),
        ('Drone Bay', 'drone', 0), ('Cargo Hold', 'cargo', 0),
    ]

    slot_groups = []
    for label, key, total_attr in slot_config:
        mods = slots_map.get(key, [])
        # Sum quantities for usage count
        used_count = sum(m['quantity'] for m in mods)
        
        if total_attr < used_count: total_attr = used_count
        
        is_hardpoint = key in ['high', 'mid', 'low', 'rig', 'subsystem']
        empties_count = max(0, total_attr - used_count) if is_hardpoint else 0
        
        slot_groups.append({
            'name': label, 
            'key': key, 
            'total': total_attr if is_hardpoint else None,
            'used': used_count if is_hardpoint else None, 
            'modules': mods,
            'empties_count': empties_count, 
            'is_hardpoint': is_hardpoint
        })

    data = {
        'id': entry.id, 
        'character_name': entry.character.character_name,
        'corp_name': entry.character.corporation_name, 
        'ship_name': hull.type_name,
        'hull_id': hull.type_id, 
        'fit_name': entry.fit.name,
        'raw_eft': entry.raw_eft, 
        'slots': slot_groups,
        'is_fc': can_inspect, 
        'status': entry.status
    }
    return JsonResponse(data)

@login_required
def fleet_overview_api(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    if not fleet.commander:
        return JsonResponse({'error': 'No commander active'}, status=404)

    fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
    if not fc_char:
        return JsonResponse({'error': 'FC has no linked characters'}, status=400)
        
    actual_fleet_id = fleet.esi_fleet_id
    
    if not actual_fleet_id:
        if check_token(fc_char):
            headers = {'Authorization': f'Bearer {fc_char.access_token}'}
            try:
                resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    actual_fleet_id = data['fleet_id']
                    fleet.esi_fleet_id = actual_fleet_id
                    fleet.save()
            except Exception:
                pass
    
    if not actual_fleet_id:
        return JsonResponse({'error': 'Could not detect active ESI Fleet'}, status=404)

    composite_data, _ = get_fleet_composition(actual_fleet_id, fc_char)
    
    if composite_data is None:
        return JsonResponse({'error': 'Failed to fetch members from ESI'}, status=500)
    elif composite_data == 'unchanged':
        return JsonResponse({'status': 'unchanged'}, status=200)

    summary, hierarchy = process_fleet_data(composite_data)

    return JsonResponse({
        'fleet_id': actual_fleet_id, 
        'member_count': len(composite_data.get('members', [])),
        'summary': summary, 
        'hierarchy': hierarchy
    })


@login_required
def fc_action(request, entry_id, action):
    if not is_fleet_command(request.user):
        return HttpResponse("Unauthorized", status=403)

    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    fleet = entry.fleet
    
    if action == 'approve':
        entry.status = 'approved'
        entry.approved_at = timezone.now()
        entry.save()
        tags = [t.name.lower() for t in entry.fit.tags.all()]
        cat_name = entry.fit.category.name.lower()
        col = 'other'
        if 'logi' in tags or 'logistics' in cat_name: col = 'logi'
        elif 'sniper' in tags: col = 'sniper'
        elif 'dps' in tags or 'brawl' in tags: col = 'dps'
        broadcast_update(fleet.id, 'move', entry, target_col=col)
        
    elif action == 'deny':
        entry.status = 'rejected'
        entry.save()
        broadcast_update(fleet.id, 'remove', entry)
        
    elif action == 'invite':
        fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
        if not fleet.esi_fleet_id:
             return JsonResponse({'success': False, 'error': 'No ESI Fleet linked. Is the FC in a fleet?'})

        success = invite_to_fleet(fleet.esi_fleet_id, fc_char, entry.character.character_id)
        if success:
            entry.status = 'invited'
            entry.invited_at = timezone.now()
            entry.save()
            tags = [t.name.lower() for t in entry.fit.tags.all()]
            cat_name = entry.fit.category.name.lower()
            col = 'other'
            if 'logi' in tags or 'logistics' in cat_name: col = 'logi'
            elif 'sniper' in tags: col = 'sniper'
            elif 'dps' in tags or 'brawl' in tags: col = 'dps'
            broadcast_update(fleet.id, 'move', entry, target_col=col)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'ESI Invite Failed'})
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_fleet_command)
def take_fleet_command(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    fleet.commander = request.user
    fleet.save()
    return redirect('fleet_dashboard', token=fleet.join_token)

# Management view uses Integer ID internally from POST forms
@login_required
@user_passes_test(can_manage_doctrines)
def manage_doctrines(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            fit_id = request.POST.get('fit_id')
            DoctrineFit.objects.filter(id=fit_id).delete()
            return redirect('manage_doctrines')
        elif action == 'create' or action == 'update':
            raw_eft = request.POST.get('eft_paste')
            cat_id = request.POST.get('category_id')
            description = request.POST.get('description', '')
            tag_ids = request.POST.getlist('tags')
            parser = EFTParser(raw_eft)
            if parser.parse():
                category = get_object_or_404(DoctrineCategory, id=cat_id)
                if action == 'update':
                    fit_id = request.POST.get('fit_id')
                    fit = get_object_or_404(DoctrineFit, id=fit_id)
                    fit.name = parser.fit_name; fit.category = category; fit.ship_type = parser.hull_obj
                    fit.eft_format = parser.raw_text; fit.description = description; fit.save()
                    fit.modules.all().delete()
                else:
                    fit = DoctrineFit.objects.create(name=parser.fit_name, category=category, ship_type=parser.hull_obj, eft_format=parser.raw_text, description=description)
                if tag_ids: fit.tags.set(tag_ids)
                else: fit.tags.clear()
                
                # FIXED: Apply slot determination logic
                for item in parser.items:
                    slot_type = _determine_slot(item['obj'])
                    FitModule.objects.create(fit=fit, item_type=item['obj'], quantity=item['quantity'], slot=slot_type)
                    
            return redirect('manage_doctrines')
    categories = DoctrineCategory.objects.all()
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'order')
    tags = DoctrineTag.objects.all()
    context = { 'categories': categories, 'fits': fits, 'tags': tags, 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/doctrines.html', context)