import requests
from django.conf import settings
from pilot_data.models import EveCharacter, ItemType

# Base ESI URL
ESI_BASE = "https://esi.evetech.net/latest"

def get_auth_header(character):
    """
    Ensures the character has a valid token and returns the auth header.
    """
    # Import locally to avoid circular imports if any
    from esi_calls.token_manager import check_token
    
    if not check_token(character):
        return None
    return {'Authorization': f'Bearer {character.access_token}'}

def get_fleet_members(fleet_id, fc_character):
    """
    Fetches the hierarchical structure of the fleet.
    Returns a dict active members grouped by role/ship.
    """
    headers = get_auth_header(fc_character)
    if not headers: return None

    url = f"{ESI_BASE}/fleets/{fleet_id}/members/"
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        print(f"ESI Error fetching fleet: {resp.status_code} - {resp.text}")
        return None
        
    members = resp.json()
    
    # Enrich data with Ship Names
    # We collect all ship_type_ids to fetch names efficiently if needed, 
    # though usually we rely on our local SDE.
    
    enriched_members = []
    
    # Pre-fetch Ship Types to avoid N+1 queries
    ship_ids = set(m['ship_type_id'] for m in members)
    ship_map = {item.type_id: item.type_name for item in ItemType.objects.filter(type_id__in=ship_ids)}
    
    for m in members:
        ship_name = ship_map.get(m['ship_type_id'], 'Unknown Ship')
        
        enriched_members.append({
            'character_id': m['character_id'],
            'solar_system_id': m['solar_system_id'],
            'ship_type_id': m['ship_type_id'],
            'ship_name': ship_name,
            'role': m['role'],
            'wing_id': m['wing_id'],
            'squad_id': m['squad_id'],
            'takes_fleet_warp': m['takes_fleet_warp']
        })
        
    return enriched_members

def invite_to_fleet(fleet_id, fc_character, target_character_id, role='squad_member', squad_id=None, wing_id=None):
    """
    Invites a character to the fleet.
    """
    headers = get_auth_header(fc_character)
    if not headers: return False
    
    url = f"{ESI_BASE}/fleets/{fleet_id}/members/"
    
    payload = {
        "character_id": target_character_id,
        "role": role
    }
    
    # Optional specific positioning
    if squad_id: payload['squad_id'] = squad_id
    elif wing_id: payload['wing_id'] = wing_id
    
    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code == 204:
        return True
    
    print(f"Invite Failed: {resp.status_code} - {resp.text}")
    return False