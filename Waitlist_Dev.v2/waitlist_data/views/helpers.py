from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from waitlist_data.models import FleetActivity, FitModule
from pilot_data.models import ItemType, TypeEffect
from waitlist_data.stats import calculate_pilot_stats
from core.eft_parser import EFTParser
from waitlist_data.fitting_service import SmartFitMatcher

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
    if not item_type: return 'cargo'
    
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

def _build_fit_analysis_response(raw_eft, fit_obj, hull_obj, character, is_fc):
    try:
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
                    # Defensive check: item['obj'] could theoretically be missing if parse failed weirdly
                    if item.get('obj'):
                        attrs = {a.attribute_id: a.value for a in item['obj'].attributes.all()}
                        if 14 in attrs: high_total += int(attrs[14])
                        if 13 in attrs: mid_total += int(attrs[13])
                        if 12 in attrs: low_total += int(attrs[12])
        else:
            high_total = mid_total = low_total = rig_total = 0

        slot_config = [
            ('High Slots', 'high', high_total), ('Mid Slots', 'mid', mid_total),
            ('Low Slots', 'low', low_total), ('Rigs', 'rig', rig_total),
            ('Subsystems', 'subsystem', 5 if hull_obj and hull_obj.group_id == 963 else 0),
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
    except Exception as e:
        # Fallback for ANY error during analysis to prevent UI hang
        print(f"Fit Analysis Error: {e}")
        return {
            'character_name': character.character_name,
            'corp_name': character.corporation_name,
            'ship_name': "Error Analysis Failed",
            'hull_id': 0,
            'fit_name': "Error",
            'raw_eft': raw_eft,
            'slots': [],
            'is_fc': is_fc,
            'error': str(e)
        }