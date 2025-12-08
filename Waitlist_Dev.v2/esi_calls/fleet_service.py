import email.utils
from django.core.cache import cache
from pilot_data.models import EveCharacter, ItemType, ItemGroup
from esi_calls.esi_network import call_esi

# Base ESI URL
ESI_BASE = "https://esi.evetech.net/latest"

def get_fleet_composition(fleet_id, fc_character):
    """
    Fetches raw fleet members AND wing structure.
    Uses Django Cache to prevent ESI spam when multiple users are dashboarding.
    Cache TTL: 10 seconds.
    """
    cache_key = f"fleet_comp_{fleet_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data, None

    # 1. Fetch Members (Force Refresh to get body)
    members_url = f"{ESI_BASE}/fleets/{fleet_id}/members/"
    members_resp = call_esi(fc_character, f'fleet_members_{fleet_id}', members_url, force_refresh=True)
    
    # 2. Fetch Wing Names (Force Refresh to get body)
    wings_url = f"{ESI_BASE}/fleets/{fleet_id}/wings/"
    wings_resp = call_esi(fc_character, f'fleet_wings_{fleet_id}', wings_url, force_refresh=True)

    # 3. Check for Errors
    if members_resp['status'] >= 400 or wings_resp['status'] >= 400:
        return None, f"ESI Error: {members_resp.get('status')} / {wings_resp.get('status')}"

    data = {
        'members': members_resp.get('data', []),
        'wings': wings_resp.get('data', [])
    }
    
    # Cache the successful result for 10 seconds
    cache.set(cache_key, data, timeout=10)
    
    return data, None

def process_fleet_data(composite_data):
    """
    Transforms raw ESI data into Summary and Hierarchy.
    Sorts Wings and Squads by ID to match In-Game order.
    """
    members = composite_data.get('members') or []
    wings_structure = composite_data.get('wings') or []

    # Sort structure by ID to ensure consistent order
    wings_structure.sort(key=lambda x: x['id'])

    summary = {}
    
    # --- 1. Initialize Tree from Structure (Preserves Order) ---
    hierarchy_wings = []
    
    # Lookups for O(1) access when placing members
    wing_lookup = {}
    squad_lookup = {}

    for w in wings_structure:
        w_obj = {
            'id': w['id'],
            'name': w['name'],
            'commander': None,
            'squads': [] 
        }
        hierarchy_wings.append(w_obj)
        wing_lookup[w['id']] = w_obj
        
        # Sort squads within wing
        squads_list = w.get('squads', [])
        squads_list.sort(key=lambda x: x['id'])
        
        for s in squads_list:
            s_obj = {
                'id': s['id'],
                'name': s['name'],
                'commander': None,
                'members': [] 
            }
            w_obj['squads'].append(s_obj)
            squad_lookup[s['id']] = s_obj

    hierarchy = {
        'commander': None,
        'wings': hierarchy_wings
    }

    # --- 2. Bulk Fetch Metadata ---
    if members:
        ship_ids = set(m['ship_type_id'] for m in members)
        char_ids = [m['character_id'] for m in members]
        
        items = ItemType.objects.filter(type_id__in=ship_ids)
        item_map = {i.type_id: i for i in items}
        
        group_ids = set(i.group_id for i in items if i.group_id)
        groups = ItemGroup.objects.filter(group_id__in=group_ids)
        group_map = {g.group_id: g.group_name for g in groups}
        
        known_chars = EveCharacter.objects.filter(character_id__in=char_ids).values('character_id', 'character_name')
        name_map = {c['character_id']: c['character_name'] for c in known_chars}
    else:
        item_map = {}
        group_map = {}
        name_map = {}

    # --- 3. Populate Members ---
    for m in members:
        ship_item = item_map.get(m['ship_type_id'])
        ship_name = ship_item.type_name if ship_item else "Unknown Ship"
        group_name = "Unknown Group"
        if ship_item:
            group_name = group_map.get(ship_item.group_id, "Unknown Group")
            
        char_name = name_map.get(m['character_id'], f"Guest ({m['character_id']})")
        
        obj = {
            'character_id': m['character_id'],
            'name': char_name,
            'ship_type_id': m['ship_type_id'],
            'ship_name': ship_name,
            'group_name': group_name,
            'role': m['role'],
            'wing_id': m['wing_id'],
            'squad_id': m['squad_id'],
            'takes_fleet_warp': m['takes_fleet_warp'],
            'join_time': m['join_time']
        }
        
        # Summary Stats
        if group_name not in summary: summary[group_name] = {}
        if ship_name not in summary[group_name]: summary[group_name][ship_name] = 0
        summary[group_name][ship_name] += 1
        
        # Tree Placement
        if m['role'] == 'fleet_commander':
            hierarchy['commander'] = obj
            
        elif m['wing_id'] > 0:
            # Dynamic Wing Creation (Safety Net for ghost wings)
            if m['wing_id'] not in wing_lookup:
                w_obj = {
                    'id': m['wing_id'],
                    'name': f"Wing {m['wing_id']}",
                    'commander': None,
                    'squads': []
                }
                # If creating dynamically, just append to end
                hierarchy['wings'].append(w_obj)
                wing_lookup[m['wing_id']] = w_obj

            if m['role'] == 'wing_commander':
                wing_lookup[m['wing_id']]['commander'] = obj
                
            elif m['squad_id'] > 0:
                # Dynamic Squad Creation (Safety Net)
                if m['squad_id'] not in squad_lookup:
                    s_obj = {
                        'id': m['squad_id'],
                        'name': f"Squad {m['squad_id']}",
                        'commander': None,
                        'members': []
                    }
                    wing_lookup[m['wing_id']]['squads'].append(s_obj)
                    squad_lookup[m['squad_id']] = s_obj

                if m['role'] == 'squad_commander':
                    squad_lookup[m['squad_id']]['commander'] = obj
                else:
                    squad_lookup[m['squad_id']]['members'].append(obj)

    return summary, hierarchy

def invite_to_fleet(fleet_id, fc_character, target_character_id, role='squad_member', squad_id=None, wing_id=None):
    from esi_calls.token_manager import check_token
    if not check_token(fc_character): return False
    
    headers = {'Authorization': f'Bearer {fc_character.access_token}'}
    url = f"{ESI_BASE}/fleets/{fleet_id}/members/"
    
    payload = {"character_id": target_character_id, "role": role}
    if squad_id: payload['squad_id'] = squad_id
    elif wing_id: payload['wing_id'] = wing_id
    
    resp = requests.post(url, headers=headers, json=payload)
    return resp.status_code == 204