import email.utils
import requests
import time
from django.core.cache import cache
from pilot_data.models import EveCharacter, ItemType, ItemGroup
from esi_calls.esi_network import call_esi, get_esi_session
from esi.models import Token # Updated import

# Base ESI URL
ESI_BASE = "https://esi.evetech.net/latest"

def _get_valid_token(character):
    """
    Helper to get a valid access token string for a character.
    Handles refresh automatically via django-esi.
    """
    token = Token.objects.filter(character_id=character.character_id).order_by('-created').first()
    if token:
        try:
            return token.valid_access_token()
        except Exception:
            return None
    return None

def get_fleet_composition(fleet_id, fc_character):
    """
    Fetches raw fleet members AND wing structure.
    Uses Django Cache to prevent ESI spam when multiple users are dashboarding.
    Cache TTL: 5 seconds (Matches ESI spec).
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
    
    # Cache the successful result for 5 seconds
    cache.set(cache_key, data, timeout=5)
    
    return data, None

def resolve_unknown_names(char_ids):
    """
    Bulk resolves character names from ESI for IDs not in our DB.
    Returns a COMPLETE map of {id: name} for all input IDs (DB + ESI).
    """
    if not char_ids: return {}
    
    resolved = {}
    
    # 1. Fetch from DB
    known_chars = EveCharacter.objects.filter(character_id__in=char_ids).values('character_id', 'character_name')
    for c in known_chars:
        resolved[c['character_id']] = c['character_name']
        
    known_ids = set(resolved.keys())
    missing_ids = list(set(char_ids) - known_ids)
    
    if not missing_ids: return resolved

    # 2. Resolve missing via ESI
    url = f"{ESI_BASE}/universe/names/"
    
    chunk_size = 500
    for i in range(0, len(missing_ids), chunk_size):
        chunk = missing_ids[i:i + chunk_size]
        try:
            resp = requests.post(url, json=chunk, timeout=3)
            if resp.status_code == 200:
                for entry in resp.json():
                    if entry['category'] == 'character':
                        resolved[entry['id']] = entry['name']
                    elif entry['category'] == 'corporation':
                        resolved[entry['id']] = entry['name']
                    elif entry['category'] == 'alliance':
                        resolved[entry['id']] = entry['name']
        except Exception as e:
            print(f"Name Resolution Error: {e}")
            
    return resolved

def process_fleet_data(composite_data, external_names=None):
    """
    Transforms raw ESI data into Summary and Hierarchy.
    """
    if external_names is None: external_names = {}
    
    members = composite_data.get('members') or []
    wings_structure = composite_data.get('wings') or []

    wings_structure.sort(key=lambda x: x['id'])

    summary = {}
    hierarchy_wings = []
    
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

    for m in members:
        ship_item = item_map.get(m['ship_type_id'])
        ship_name = ship_item.type_name if ship_item else "Unknown Ship"
        group_name = "Unknown Group"
        if ship_item:
            group_name = group_map.get(ship_item.group_id, "Unknown Group")
            
        char_name = name_map.get(m['character_id'])
        if not char_name:
            char_name = external_names.get(m['character_id'], f"Guest ({m['character_id']})")
        
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
        
        if group_name not in summary: summary[group_name] = {}
        if ship_name not in summary[group_name]: summary[group_name][ship_name] = 0
        summary[group_name][ship_name] += 1
        
        if m['role'] == 'fleet_commander':
            hierarchy['commander'] = obj
            
        elif m['wing_id'] > 0:
            if m['wing_id'] not in wing_lookup:
                w_obj = {
                    'id': m['wing_id'],
                    'name': f"Wing {m['wing_id']}",
                    'commander': None,
                    'squads': []
                }
                hierarchy['wings'].append(w_obj)
                wing_lookup[m['wing_id']] = w_obj

            if m['role'] == 'wing_commander':
                wing_lookup[m['wing_id']]['commander'] = obj
                
            elif m['squad_id'] > 0:
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
    access_token = _get_valid_token(fc_character)
    if not access_token:
        return False, "FC Token Expired"
    
    headers = {'Authorization': f'Bearer {access_token}'}
    url = f"{ESI_BASE}/fleets/{fleet_id}/members/"
    
    payload = {"character_id": target_character_id, "role": role}
    if squad_id: payload['squad_id'] = squad_id
    elif wing_id: payload['wing_id'] = wing_id
    
    try:
        session = get_esi_session()
        resp = session.post(url, headers=headers, json=payload, timeout=5)
        
        if resp.status_code == 204:
            return True, "Invite Sent"
        
        error_msg = f"ESI {resp.status_code}"
        try:
            data = resp.json()
            if 'error' in data: error_msg = data['error']
        except:
            pass
            
        print(f"Invite Failed: {error_msg}")
        return False, error_msg
        
    except Exception as e:
        return False, f"Network Error: {str(e)}"

def update_fleet_settings(fleet_id, fc_character, motd=None, is_free_move=None):
    access_token = _get_valid_token(fc_character)
    if not access_token:
        return False, "FC Token Expired"

    url = f"{ESI_BASE}/fleets/{fleet_id}/"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    payload = {}
    if motd is not None: payload['motd'] = motd
    if is_free_move is not None: payload['is_free_move'] = is_free_move
        
    if not payload: return True, "No changes"

    try:
        session = get_esi_session()
        resp = session.put(url, headers=headers, json=payload, timeout=5)
        if resp.status_code == 204: return True, "Settings Updated"
        error_msg = f"ESI {resp.status_code}"
        try:
            if 'error' in resp.json(): error_msg = resp.json()['error']
        except: pass
        return False, error_msg
    except Exception as e:
        return False, f"Network Error: {str(e)}"

# --- FLEET STRUCTURE MANAGEMENT (Full Sync) ---

def sync_fleet_structure(fleet_id, fc_character, desired_structure):
    """
    Synchronizes in-game structure to match desired structure exactly (Create/Rename/Delete).
    """
    # NOTE: check_token was here, but we now check validity implicitly when getting tokens for operations
    # However, for robustness, we can check initially.
    if not _get_valid_token(fc_character):
        return False, "FC Token Expired"

    # 1. Fetch Current State
    current_data, error = get_fleet_composition(fleet_id, fc_character)
    if error: return False, error
    
    current_wings = current_data.get('wings', [])
    # Sort by ID to ensure stable mapping
    current_wings.sort(key=lambda x: x['id'])
    
    logs = []
    
    # 2. DELETE Extra Wings (Prune from end)
    while len(current_wings) > len(desired_structure):
        last_wing = current_wings.pop()
        time.sleep(0.5)
        if _delete_wing(fc_character, fleet_id, last_wing['id']):
            logs.append(f"Deleted Wing {last_wing['name']}")
    
    # 3. Process remaining desired wings
    for i, desired_wing in enumerate(desired_structure):
        wing_id = None
        
        # A. Get or Create Wing
        if i < len(current_wings):
            # Existing
            wing_data = current_wings[i]
            wing_id = wing_data['id']
            if wing_data['name'] != desired_wing['name']:
                time.sleep(0.5)
                if _rename_entity(fc_character, fleet_id, 'wings', wing_id, desired_wing['name']):
                    logs.append(f"Renamed Wing {wing_id} -> {desired_wing['name']}")
        else:
            # New
            time.sleep(0.5)
            wing_id = _create_wing(fc_character, fleet_id)
            if wing_id:
                time.sleep(0.5)
                _rename_entity(fc_character, fleet_id, 'wings', wing_id, desired_wing['name'])
                logs.append(f"Created Wing {desired_wing['name']}")
                current_wings.append({'id': wing_id, 'squads': []}) # Update local model
            else:
                logs.append(f"Failed to create wing {desired_wing['name']}")
                continue

        # B. Sync Squads
        if wing_id:
            # Determine current squads for this wing
            # If it was existing, use fetched data. If new, it's empty.
            current_squads = []
            if i < len(current_wings):
                # NOTE: current_wings[i] here refers to the snapshot we fetched/updated
                current_squads = current_wings[i].get('squads', [])
                current_squads.sort(key=lambda x: x['id'])

            desired_squads = desired_wing.get('squads', [])

            # DELETE Extra Squads
            while len(current_squads) > len(desired_squads):
                last_squad = current_squads.pop()
                time.sleep(0.5)
                if _delete_squad(fc_character, fleet_id, last_squad['id']):
                    logs.append(f"Deleted Squad {last_squad['name']}")

            # CREATE / RENAME Squads
            for j, desired_squad_name in enumerate(desired_squads):
                squad_id = None
                
                if j < len(current_squads):
                    # Existing
                    squad_data = current_squads[j]
                    squad_id = squad_data['id']
                    if squad_data['name'] != desired_squad_name:
                        time.sleep(0.5)
                        _rename_entity(fc_character, fleet_id, 'squads', squad_id, desired_squad_name, wing_id=wing_id)
                else:
                    # New
                    time.sleep(0.5)
                    squad_id = _create_squad(fc_character, fleet_id, wing_id)
                    if squad_id:
                        time.sleep(0.5)
                        _rename_entity(fc_character, fleet_id, 'squads', squad_id, desired_squad_name, wing_id=wing_id)
    
    return True, logs

def _create_wing(character, fleet_id):
    access_token = _get_valid_token(character)
    if not access_token: return None
    url = f"{ESI_BASE}/fleets/{fleet_id}/wings/"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        session = get_esi_session()
        resp = session.post(url, headers=headers)
        if resp.status_code == 201: return resp.json()['wing_id']
    except: pass
    return None

def _create_squad(character, fleet_id, wing_id):
    access_token = _get_valid_token(character)
    if not access_token: return None
    url = f"{ESI_BASE}/fleets/{fleet_id}/wings/{wing_id}/squads/"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        session = get_esi_session()
        resp = session.post(url, headers=headers)
        if resp.status_code == 201: return resp.json()['squad_id']
    except: pass
    return None

def _delete_wing(character, fleet_id, wing_id):
    access_token = _get_valid_token(character)
    if not access_token: return False
    url = f"{ESI_BASE}/fleets/{fleet_id}/wings/{wing_id}/"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        session = get_esi_session()
        resp = session.delete(url, headers=headers)
        return resp.status_code == 204
    except: return False

def _delete_squad(character, fleet_id, squad_id):
    access_token = _get_valid_token(character)
    if not access_token: return False
    # Squad delete URL is flat: /fleets/{fleet_id}/squads/{squad_id}/
    url = f"{ESI_BASE}/fleets/{fleet_id}/squads/{squad_id}/"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        session = get_esi_session()
        resp = session.delete(url, headers=headers)
        return resp.status_code == 204
    except: return False

def _rename_entity(character, fleet_id, entity_type, entity_id, new_name, wing_id=None):
    access_token = _get_valid_token(character)
    if not access_token: return False
    url = ""
    if entity_type == 'wings':
        url = f"{ESI_BASE}/fleets/{fleet_id}/wings/{entity_id}/"
    elif entity_type == 'squads':
        url = f"{ESI_BASE}/fleets/{fleet_id}/squads/{entity_id}/"
    
    headers = {'Authorization': f'Bearer {access_token}'}
    payload = {'name': new_name}
    
    try:
        session = get_esi_session()
        resp = session.put(url, headers=headers, json=payload)
        return resp.status_code in [200, 204]
    except Exception as e:
        print(f"Error renaming entity: {e}")
        return False
