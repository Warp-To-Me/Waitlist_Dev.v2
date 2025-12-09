from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import requests 
from collections import defaultdict
import json
import re

# Core Imports
from core.utils import get_role_priority, ROLE_HIERARCHY
from core.eft_parser import EFTParser
from core.models import Capability 

# Permissions
from core.permissions import (
    get_template_base, 
    is_fleet_command, 
    can_manage_doctrines, 
    can_view_fleet_overview,
    get_mgmt_context
)

# Model Imports
from pilot_data.models import EveCharacter, TypeEffect, ItemGroup, CharacterImplant, ItemType
from .models import (
    DoctrineCategory, DoctrineFit, FitModule, DoctrineTag, 
    Fleet, WaitlistEntry, FleetActivity, 
    FleetStructureTemplate, StructureWing, StructureSquad
)

# ESI Services
from esi_calls.fleet_service import (
    get_fleet_composition, process_fleet_data, invite_to_fleet, 
    sync_fleet_structure, update_fleet_settings, ESI_BASE
)
from esi_calls.token_manager import check_token

# Fitting Service
from .fitting_service import SmartFitMatcher, FitComparator, ComparisonStatus

# Stats Service
from .stats import batch_calculate_pilot_stats, calculate_pilot_stats

# --- HELPERS ---

def _log_fleet_action(fleet, character, action, actor=None, ship_type=None, details="", eft_text=None):
    hull_name = ""
    hull_id = None
    
    if ship_type:
        hull_name = ship_type.type_name
        hull_id = ship_type.type_id
    elif character and character.current_ship_type_id:
        hull_name = character.current_ship_name 
        hull_id = character.current_ship_type_id
        try:
            it = ItemType.objects.get(type_id=hull_id)
            hull_name = it.type_name
        except:
            hull_name = "Unknown Ship"

    FleetActivity.objects.create(
        fleet=fleet,
        character=character,
        actor=actor,
        action=action,
        ship_name=hull_name,
        hull_id=hull_id,
        details=details,
        fit_eft=eft_text
    )

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
    Determines the slot layout (High/Mid/Low/Rig) based on Dogma Effects.
    """
    effects = set(TypeEffect.objects.filter(item=item_type).values_list('effect_id', flat=True))
    if 12 in effects: return 'high'  # hiPower
    if 13 in effects: return 'mid'   # medPower
    if 11 in effects: return 'low'   # loPower
    if 2663 in effects: return 'rig' # rigSlot
    try:
        if item_type.group:
            cat_id = item_type.group.category_id
            if cat_id == 32: return 'subsystem'
            if cat_id == 18 or cat_id == 87: return 'drone'
            if cat_id == 8: return 'cargo'
    except Exception:
        pass
    return 'cargo'

# --- RECURSIVE COLUMN LOGIC ---
def _resolve_column(category_id, category_map):
    """
    Starts at the child category (Leaf) and walks UP the tree.
    Returns the first specific column assignment found.
    This enables 'Child Overrides Parent' behavior.
    """
    current_id = category_id
    
    # Safety limit to prevent infinite loops (max depth 10)
    for _ in range(10):
        if not current_id: break
        
        cat_data = category_map.get(current_id)
        if not cat_data: break
        
        # If explicit column found (and not inheriting), return it immediately
        if cat_data['target'] != 'inherit':
            return cat_data['target']
            
        # If 'inherit', move to parent and loop again
        current_id = cat_data['parent_id']
        
    return 'other' # Default fallback if root is reached without a setting

def broadcast_update(fleet_id, action, entry, target_col=None):
    channel_layer = get_channel_layer()
    group_name = f'fleet_{fleet_id}'
    payload = {
        'type': 'fleet_update',
        'action': action,
        'entry_id': entry.id
    }
    if action in ['add', 'move']:
        stats = calculate_pilot_stats(entry.character)
        hull_name = entry.hull.type_name if entry.hull else "Unknown"
        hull_seconds = stats['hull_breakdown'].get(hull_name, 0)
        
        entry.display_stats = {
            'total_hours': stats['total_hours'],
            'hull_hours': round(hull_seconds / 3600, 1)
        }
        
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
    aggregated = {}
    for mod in raw_modules:
        key = (mod.slot, mod.item_type.type_id)
        if key not in aggregated:
            aggregated[key] = {
                'name': mod.item_type.type_name, 'id': mod.item_type.type_id,
                'quantity': 0, 'slot': mod.slot
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
    
    if hull.group_id == 963:
        for mod in raw_modules:
            attrs = {a.attribute_id: a.value for a in mod.item_type.attributes.all()}
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
        mods = modules_by_slot.get(key, [])
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


# --- FLEET SETUP FLOW ---

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

# --- DELETE TEMPLATE ---
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

# --- ACTIVE FLEET SETTINGS VIEW ---

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

# --- NEW: CLOSE FLEET API ---
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


# --- EXISTING FLEET VIEWS ---

@login_required
def fleet_dashboard(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    fc_name = EveCharacter.objects.filter(user=fleet.commander, is_main=True).values_list('character_name', flat=True).first()
    if not fc_name:
        fc_name = EveCharacter.objects.filter(user=fleet.commander).values_list('character_name', flat=True).first()
    if not fc_name:
        fc_name = fleet.commander.username

    entries = WaitlistEntry.objects.filter(fleet=fleet).exclude(status__in=['rejected', 'left']).select_related(
        'character', 'fit', 'fit__ship_type', 'fit__category', 'hull'
    ).order_by('created_at')

    char_ids = [e.character.character_id for e in entries]
    all_stats = batch_calculate_pilot_stats(char_ids)
    
    columns = {'pending': [], 'logi': [], 'dps': [], 'sniper': [], 'other': []}
    
    # --- BUILD CATEGORY MAP FOR RECURSIVE LOOKUP ---
    # Fetch all categories to build the inheritance tree in memory (O(1) lookups)
    # This prevents N+1 queries during the recursive bubbling
    all_cats = DoctrineCategory.objects.values('id', 'parent_id', 'target_column')
    category_map = {
        c['id']: {'parent_id': c['parent_id'], 'target': c['target_column']}
        for c in all_cats
    }

    for entry in entries:
        stats = all_stats.get(entry.character.character_id, {})
        hull_name = entry.hull.type_name if entry.hull else "Unknown"
        hull_seconds = stats.get('hull_breakdown', {}).get(hull_name, 0)
        
        entry.display_stats = {
            'total_hours': stats.get('total_hours', 0),
            'hull_hours': round(hull_seconds / 3600, 1)
        }

        if entry.status == 'pending':
            columns['pending'].append(entry)
        elif entry.fit:
            # --- RECURSIVE COLUMN RESOLUTION ---
            # Start at Leaf (entry.fit.category) and check if it has a setting.
            # If 'inherit', bubble up.
            target = _resolve_column(entry.fit.category.id, category_map)
            
            if target in columns:
                columns[target].append(entry)
            else:
                columns['other'].append(entry)
        else:
            columns['other'].append(entry)

    user_chars = request.user.characters.filter(x_up_visible=True).prefetch_related('implants')
    
    implant_type_ids = set()
    for char in user_chars:
        for imp in char.implants.all():
            implant_type_ids.add(imp.type_id)
            
    item_map = ItemType.objects.filter(type_id__in=implant_type_ids).in_bulk(field_name='type_id')
    
    for char in user_chars:
        char.active_implants = []
        for imp in char.implants.all():
            item = item_map.get(imp.type_id)
            if item:
                char.active_implants.append({
                    'name': item.type_name,
                    'id': item.type_id
                })

    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related('subcategories__fits')
    can_view_overview = can_view_fleet_overview(request.user)

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
def fleet_history_view(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    if not is_fleet_command(request.user):
        return render(request, 'access_denied.html', {'base_template': get_template_base(request)})

    logs = FleetActivity.objects.filter(fleet=fleet).select_related('character', 'actor', 'character__user').order_by('-timestamp')
    
    total_xups = logs.filter(action='x_up').count()
    total_kills = logs.filter(action__in=['denied', 'kicked']).count()
    unique_pilots = logs.values('character').distinct().count()
    
    context = {
        'fleet': fleet,
        'logs': logs,
        'stats': {
            'xups': total_xups,
            'removals': total_kills,
            'pilots': unique_pilots
        },
        'base_template': get_template_base(request)
    }
    return render(request, 'waitlist/history.html', context)

@login_required
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
            
            entry = WaitlistEntry.objects.select_related('character__user', 'fit', 'hull', 'fit__ship_type', 'fit__category').get(id=entry.id)

            broadcast_update(fleet.id, 'add', entry, target_col='pending')
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

    broadcast_update(entry.fleet.id, 'move', entry, target_col='pending')
    
    return JsonResponse({'success': True, 'message': f"Updated to: {new_fit_name}"})

@login_required
@require_POST
def leave_fleet(request, entry_id):
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    if entry.character.user != request.user: return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    
    fleet_id = entry.fleet.id
    
    _log_fleet_action(entry.fleet, entry.character, 'left_waitlist', actor=request.user, details="User initiated leave")
    
    entry.delete()
    broadcast_update(fleet_id, 'remove', entry)
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

def _build_fit_analysis_response(raw_eft, fit_obj, hull_obj, character, is_fc):
    parser = EFTParser(raw_eft)
    parser.parse() 
    
    if not hull_obj and fit_obj: hull_obj = fit_obj.ship_type
    if not hull_obj: hull_obj = parser.hull_obj

    if fit_obj:
        matcher = SmartFitMatcher(parser)
        _, analysis = matcher._score_fit(fit_obj)
        
        aggregated = {}
        for item in analysis:
            slot_key = item['slot']
            status = item['status']
            p_id = item['pilot_item'].type_id if item['pilot_item'] else 0
            d_id = item['doctrine_item'].type_id if item['doctrine_item'] else 0
            p_name = item['pilot_item'].type_name if item['pilot_item'] else None
            d_name = item['doctrine_item'].type_name if item['doctrine_item'] else None
            group_key = (slot_key, p_id, d_id, status)
            if group_key not in aggregated:
                aggregated[group_key] = {
                    'name': p_name or d_name or "Empty", 'id': p_id or d_id,
                    'quantity': 0, 'status': status, 'diffs': item['diffs'],
                    'doctrine_name': d_name, 'slot': slot_key
                }
            aggregated[group_key]['quantity'] += 1
    else:
        aggregated = {}
        for item in parser.items:
            item_obj = item['obj']
            slot_key = _determine_slot(item_obj)
            
            key = (slot_key, item_obj.type_id)
            if key not in aggregated:
                aggregated[key] = {
                    'name': item_obj.type_name,
                    'id': item_obj.type_id,
                    'quantity': 0,
                    'status': 'MATCH', # Neutral status
                    'diffs': [],
                    'doctrine_name': None,
                    'slot': slot_key
                }
            aggregated[key]['quantity'] += item['quantity']

    slots_map = { 'high': [], 'mid': [], 'low': [], 'rig': [], 'subsystem': [], 'drone': [], 'cargo': [] }
    for data in aggregated.values():
        s = data['slot']
        if s not in slots_map: s = 'cargo'
        slots_map[s].append(data)

    if hull_obj:
        high_total = int(hull_obj.high_slots)
        mid_total = int(hull_obj.mid_slots)
        low_total = int(hull_obj.low_slots)
        rig_total = int(hull_obj.rig_slots)
        
        if hull_obj.group_id == 963:
            for item in parser.items:
                attrs = {a.attribute_id: a.value for a in item['obj'].attributes.all()}
                if 14 in attrs: high_total += int(attrs[14])
                if 13 in attrs: mid_total += int(attrs[13])
                if 12 in attrs: low_total += int(attrs[12])
    else:
        high_total = mid_total = low_total = rig_total = 0

    slot_config = [
        ('High Slots', 'high', high_total), ('Mid Slots', 'mid', mid_total),
        ('Low Slots', 'low', low_total), ('Rigs', 'rig', rig_total),
        ('Subsystems', 'subsystem', 5 if hull.group_id == 963 else 0),
        ('Drone Bay', 'drone', 0), ('Cargo Hold', 'cargo', 0),
    ]

    slot_groups = []
    for label, key, total_attr in slot_config:
        mods = slots_map.get(key, [])
        used_count = sum(m['quantity'] for m in mods)
        
        if total_attr < used_count: total_attr = used_count
        is_hardpoint = key in ['high', 'mid', 'low', 'rig', 'subsystem']
        empties_count = max(0, total_attr - used_count) if is_hardpoint else 0
        
        slot_groups.append({
            'name': label, 'key': key, 'total': total_attr if is_hardpoint else None,
            'used': used_count if is_hardpoint else None, 'modules': mods,
            'empties_count': empties_count, 'is_hardpoint': is_hardpoint
        })

    return {
        'character_name': character.character_name,
        'corp_name': character.corporation_name, 
        'ship_name': hull_obj.type_name if hull_obj else "Unknown Ship",
        'hull_id': hull_obj.type_id if hull_obj else 0, 
        'fit_name': fit_obj.name if fit_obj else "Custom Fit",
        'raw_eft': raw_eft, 
        'slots': slot_groups,
        'is_fc': is_fc
    }

@login_required
def fleet_overview_api(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    if not fleet.commander: return JsonResponse({'error': 'No commander'}, status=404)
    fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
    if not fc_char: return JsonResponse({'error': 'FC has no characters'}, status=400)
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
            except Exception: pass
    if not actual_fleet_id: return JsonResponse({'error': 'No ESI Fleet'}, status=404)
    composite_data, _ = get_fleet_composition(actual_fleet_id, fc_char)
    if composite_data is None: return JsonResponse({'error': 'ESI Fail'}, status=500)
    elif composite_data == 'unchanged': return JsonResponse({'status': 'unchanged'}, status=200)
    summary, hierarchy = process_fleet_data(composite_data)
    return JsonResponse({'fleet_id': actual_fleet_id, 'member_count': len(composite_data.get('members', [])), 'summary': summary, 'hierarchy': hierarchy})

@login_required
def fc_action(request, entry_id, action):
    if not is_fleet_command(request.user): return HttpResponse("Unauthorized", status=403)
    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    fleet = entry.fleet
    if action == 'approve':
        entry.status = 'approved'; entry.approved_at = timezone.now(); entry.save()
        hull_for_log = entry.hull if entry.hull else entry.fit.ship_type if entry.fit else None
        _log_fleet_action(fleet, entry.character, 'approved', actor=request.user, ship_type=hull_for_log)
        
        # --- RECURSIVE SORTING ---
        col = 'other'
        if entry.fit:
            # Re-used logic for FC action broadcast
            curr_cat = entry.fit.category
            for _ in range(10):
                if not curr_cat: break
                if curr_cat.target_column != 'inherit':
                    col = curr_cat.target_column
                    break
                curr_cat = curr_cat.parent
        
        broadcast_update(fleet.id, 'move', entry, target_col=col)
    elif action == 'deny':
        hull_for_log = entry.hull if entry.hull else entry.fit.ship_type if entry.fit else None
        _log_fleet_action(fleet, entry.character, 'denied', actor=request.user, ship_type=hull_for_log, details="Manual FC Rejection")
        entry.status = 'rejected'; entry.save()
        broadcast_update(fleet.id, 'remove', entry)
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
            
            # --- RECURSIVE SORTING ---
            col = 'other'
            if entry.fit:
                curr_cat = entry.fit.category
                for _ in range(10):
                    if not curr_cat: break
                    if curr_cat.target_column != 'inherit':
                        col = curr_cat.target_column
                        break
                    curr_cat = curr_cat.parent
                    
            broadcast_update(fleet.id, 'move', entry, target_col=col)
            return JsonResponse({'success': True})
        else: return JsonResponse({'success': False, 'error': f'Invite Failed: {msg}'})
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_fleet_command)
def take_fleet_command(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    fleet.commander = request.user
    fleet.save()
    return redirect('fleet_dashboard', token=fleet.join_token)

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
                for item in parser.items:
                    slot = _determine_slot(item['obj'])
                    FitModule.objects.create(fit=fit, item_type=item['obj'], quantity=item['quantity'], slot=slot)
            return redirect('manage_doctrines')
    categories = DoctrineCategory.objects.all()
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'order')
    tags = DoctrineTag.objects.all()
    context = { 'categories': categories, 'fits': fits, 'tags': tags, 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/doctrines.html', context)