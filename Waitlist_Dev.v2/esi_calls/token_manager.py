import requests
import base64
import os
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from pilot_data.models import EveCharacter, ItemType, CharacterSkill, CharacterQueue, CharacterImplant, CharacterHistory, SkillHistory, EsiHeaderCache
from esi_calls.esi_network import call_esi

# --- QUANTIFIED ESI ENDPOINTS ---
ENDPOINT_ONLINE = 'online'
ENDPOINT_SKILLS = 'skills'
ENDPOINT_QUEUE = 'queue'
ENDPOINT_SHIP = 'ship'
ENDPOINT_WALLET = 'wallet'
ENDPOINT_LP = 'lp'
ENDPOINT_IMPLANTS = 'implants'
ENDPOINT_PUBLIC_INFO = 'public_info'
ENDPOINT_HISTORY = 'history'

ALL_ENDPOINTS = [
    ENDPOINT_ONLINE, ENDPOINT_SKILLS, ENDPOINT_QUEUE, ENDPOINT_SHIP, ENDPOINT_WALLET, 
    ENDPOINT_LP, ENDPOINT_IMPLANTS, ENDPOINT_PUBLIC_INFO, ENDPOINT_HISTORY
]

# List of endpoints that are pointless to check if the user is offline
# We will auto-skip these to save API calls.
SKIP_IF_OFFLINE = [ENDPOINT_SHIP, ENDPOINT_IMPLANTS]

def check_token(character):
    if not character.refresh_token: return False
    if not character.token_expires or character.token_expires <= timezone.now() + timedelta(minutes=5):
        print(f"Refreshing token for {character.character_name}...")
        return _refresh_access_token(character)
    return True

def _refresh_access_token(character):
    url = "https://login.eveonline.com/v2/oauth/token"
    client_id = settings.EVE_CLIENT_ID
    secret_key = os.getenv('EVE_SECRET_KEY')
    
    if not secret_key:
        print("ERROR: EVE_SECRET_KEY is missing from .env file!")
        return False
    
    try:
        response = requests.post(
            url,
            data={'grant_type': 'refresh_token', 'refresh_token': character.refresh_token},
            auth=(client_id, secret_key) 
        )
        if response.status_code != 200: return False
        response.raise_for_status()
        tokens = response.json()
        
        character.access_token = tokens['access_token']
        character.refresh_token = tokens.get('refresh_token', character.refresh_token) 
        character.token_expires = timezone.now() + timedelta(seconds=tokens['expires_in'])
        character.save()
        return True
    except Exception as e:
        print(f"Exception refreshing token: {e}")
        return False

def update_character_data(character, target_endpoints=None):
    """
    Updates character data from ESI.
    """
    if not check_token(character): return False
    base_url = "https://esi.evetech.net/latest/characters/{char_id}"
    char_id = character.character_id

    if target_endpoints is None:
        target_endpoints = list(ALL_ENDPOINTS) # Copy to avoid mutation issues

    try:
        def check_critical_error(response):
            if response['status'] >= 500:
                print(f"  !!! CRITICAL ESI ERROR {response['status']}. Aborting update for {character.character_name}.")
                return True
            return False

        # --- ONLINE STATUS (The Gatekeeper) ---
        if ENDPOINT_ONLINE in target_endpoints:
            resp = call_esi(character, ENDPOINT_ONLINE, f"{base_url.format(char_id=char_id)}/online/")
            
            if resp['status'] == 403:
                print(f"  !!! Missing Scope 'esi-location.read_online.v1' for {character.character_name}")
            
            elif not check_critical_error(resp) and resp['status'] == 200:
                data = resp['data']
                is_online = data.get('online', False)
                
                if hasattr(character, 'is_online'):
                    character.is_online = is_online
                if hasattr(character, 'last_login_at'):
                    character.last_login_at = data.get('last_login')

                # --- FILTER LOGIC (Updated for Multiple Endpoints) ---
                if not is_online:
                    # If offline, check our Skip List
                    for ep in SKIP_IF_OFFLINE:
                        if ep in target_endpoints:
                            print(f"  -> [FILTER] {character.character_name} is OFFLINE. Skipping {ep}.")
                            target_endpoints.remove(ep)
                            
                            # CRITICAL FIX: Touch cache timer so Dispatcher knows we "checked" it.
                            # Setting expires to NOW pushes it into the 15-minute throttle window.
                            EsiHeaderCache.objects.update_or_create(
                                character=character,
                                endpoint_name=ep,
                                defaults={'expires': timezone.now()}
                            )

        # --- SKILLS ---
        if ENDPOINT_SKILLS in target_endpoints:
            resp = call_esi(character, ENDPOINT_SKILLS, f"{base_url.format(char_id=char_id)}/skills/")
            if not check_critical_error(resp) and resp['status'] == 200:
                data = resp['data']
                character.total_sp = data.get('total_sp', 0)
                
                old_skills_map = {s.skill_id: s for s in CharacterSkill.objects.filter(character=character)}
                history_buffer = []
                
                for s_data in data.get('skills', []):
                    sid = s_data['skill_id']
                    new_level = s_data['active_skill_level']
                    new_sp = s_data['skillpoints_in_skill']
                    
                    if sid in old_skills_map:
                        old_s = old_skills_map[sid]
                        if old_s.active_skill_level != new_level or old_s.skillpoints_in_skill != new_sp:
                            history_buffer.append(SkillHistory(
                                character=character, skill_id=sid, old_level=old_s.active_skill_level,
                                new_level=new_level, old_sp=old_s.skillpoints_in_skill, new_sp=new_sp
                            ))
                    else:
                        history_buffer.append(SkillHistory(
                            character=character, skill_id=sid, old_level=0,
                            new_level=new_level, old_sp=0, new_sp=new_sp
                        ))
                
                if history_buffer: SkillHistory.objects.bulk_create(history_buffer)

                CharacterSkill.objects.filter(character=character).delete()
                new_skills = [
                    CharacterSkill(
                        character=character, skill_id=s['skill_id'],
                        active_skill_level=s['active_skill_level'], skillpoints_in_skill=s['skillpoints_in_skill']
                    ) for s in data.get('skills', [])
                ]
                CharacterSkill.objects.bulk_create(new_skills)

        # --- SKILL QUEUE ---
        if ENDPOINT_QUEUE in target_endpoints:
            resp = call_esi(character, ENDPOINT_QUEUE, f"{base_url.format(char_id=char_id)}/skillqueue/")
            if not check_critical_error(resp) and resp['status'] == 200:
                CharacterQueue.objects.filter(character=character).delete()
                new_queue = [
                    CharacterQueue(
                        character=character, skill_id=item['skill_id'],
                        finished_level=item['finished_level'], queue_position=item['queue_position'],
                        finish_date=item.get('finish_date')
                    ) for item in resp['data']
                ]
                CharacterQueue.objects.bulk_create(new_queue)

        # --- SHIP ---
        if ENDPOINT_SHIP in target_endpoints:
            resp = call_esi(character, ENDPOINT_SHIP, f"{base_url.format(char_id=char_id)}/ship/")
            if not check_critical_error(resp) and resp['status'] == 200:
                data = resp['data']
                character.current_ship_name = data.get('ship_name', 'Unknown')
                character.current_ship_type_id = data.get('ship_type_id')

        # --- WALLET BALANCE ---
        if ENDPOINT_WALLET in target_endpoints:
            resp = call_esi(character, ENDPOINT_WALLET, f"{base_url.format(char_id=char_id)}/wallet/")
            if not check_critical_error(resp):
                if resp['status'] == 200:
                    character.wallet_balance = resp['data']
                elif resp['status'] == 403:
                    print(f"  !!! Missing Scopes for Wallet: {character.character_name}")

        # --- LOYALTY POINTS ---
        if ENDPOINT_LP in target_endpoints:
            resp = call_esi(character, ENDPOINT_LP, f"{base_url.format(char_id=char_id)}/loyalty/points/")
            if not check_critical_error(resp):
                if resp['status'] == 200:
                    concord_entry = next((item for item in resp['data'] if item['corporation_id'] == 1000125), None)
                    character.concord_lp = concord_entry['loyalty_points'] if concord_entry else 0
                elif resp['status'] == 403:
                    print(f"  !!! Missing Scopes for LP: {character.character_name}")

        # --- IMPLANTS ---
        if ENDPOINT_IMPLANTS in target_endpoints:
            resp = call_esi(character, ENDPOINT_IMPLANTS, f"{base_url.format(char_id=char_id)}/implants/")
            if not check_critical_error(resp) and resp['status'] == 200:
                CharacterImplant.objects.filter(character=character).delete()
                new_implants = [CharacterImplant(character=character, type_id=imp_id) for imp_id in resp['data']]
                CharacterImplant.objects.bulk_create(new_implants)

        # --- PUBLIC INFO ---
        if ENDPOINT_PUBLIC_INFO in target_endpoints:
            resp = call_esi(character, ENDPOINT_PUBLIC_INFO, f"{base_url.format(char_id=char_id)}/")
            if not check_critical_error(resp) and resp['status'] == 200:
                data = resp['data']
                character.corporation_id = data.get('corporation_id')
                character.alliance_id = data.get('alliance_id')
                
                names_to_resolve = {character.corporation_id}
                if character.alliance_id: names_to_resolve.add(character.alliance_id)
                
                name_resp = requests.post("https://esi.evetech.net/latest/universe/names/", json=list(names_to_resolve))
                if name_resp.status_code == 200:
                    for entry in name_resp.json():
                        if entry['id'] == character.corporation_id:
                            character.corporation_name = entry['name']
                        elif entry['id'] == character.alliance_id:
                            character.alliance_name = entry['name']

        # --- HISTORY ---
        if ENDPOINT_HISTORY in target_endpoints:
            resp = call_esi(character, ENDPOINT_HISTORY, f"{base_url.format(char_id=char_id)}/corporationhistory/")
            if not check_critical_error(resp) and resp['status'] == 200:
                CharacterHistory.objects.filter(character=character).delete()
                history_data = resp['data']
                corp_ids = set(h['corporation_id'] for h in history_data)
                corp_names = {}
                if corp_ids:
                    name_resp = requests.post("https://esi.evetech.net/latest/universe/names/", json=list(corp_ids))
                    if name_resp.status_code == 200:
                        for entry in name_resp.json():
                            corp_names[entry['id']] = entry['name']
                new_history = [
                    CharacterHistory(
                        character=character, corporation_id=h['corporation_id'],
                        corporation_name=corp_names.get(h['corporation_id'], f"Unknown ({h['corporation_id']})"),
                        start_date=h['start_date']
                    ) for h in history_data
                ]
                CharacterHistory.objects.bulk_create(new_history)

        # Save all updated fields
        character.last_updated = timezone.now()
        character.save() 

        return True

    except Exception as e:
        print(f"ESI Update Process Error: {e}")
        return False