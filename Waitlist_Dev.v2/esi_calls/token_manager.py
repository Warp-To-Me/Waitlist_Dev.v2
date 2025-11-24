import requests
import base64
import os
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from pilot_data.models import EveCharacter, ItemType, CharacterSkill, CharacterQueue, CharacterImplant, CharacterHistory
from esi_calls.esi_network import call_esi

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

def update_character_data(character):
    if not check_token(character): return False
    base_url = "https://esi.evetech.net/latest/characters/{char_id}"
    char_id = character.character_id

    try:
        # --- SKILLS ---
        resp = call_esi(character, 'skills', f"{base_url.format(char_id=char_id)}/skills/")
        if resp['status'] == 200:
            data = resp['data']
            character.total_sp = data.get('total_sp', 0)
            # Note: character.save() is moved to the end to ensure it runs even on 304
            CharacterSkill.objects.filter(character=character).delete()
            new_skills = [
                CharacterSkill(
                    character=character,
                    skill_id=s['skill_id'],
                    active_skill_level=s['active_skill_level'],
                    skillpoints_in_skill=s['skillpoints_in_skill']
                ) for s in data.get('skills', [])
            ]
            CharacterSkill.objects.bulk_create(new_skills)

        # --- SKILL QUEUE ---
        resp = call_esi(character, 'queue', f"{base_url.format(char_id=char_id)}/skillqueue/")
        if resp['status'] == 200:
            CharacterQueue.objects.filter(character=character).delete()
            new_queue = [
                CharacterQueue(
                    character=character,
                    skill_id=item['skill_id'],
                    finished_level=item['finished_level'],
                    queue_position=item['queue_position'],
                    finish_date=item.get('finish_date')
                ) for item in resp['data']
            ]
            CharacterQueue.objects.bulk_create(new_queue)

        # --- SHIP ---
        resp = call_esi(character, 'ship', f"{base_url.format(char_id=char_id)}/ship/")
        if resp['status'] == 200:
            data = resp['data']
            character.current_ship_name = data.get('ship_name', 'Unknown')
            character.current_ship_type_id = data.get('ship_type_id')

        # --- IMPLANTS ---
        resp = call_esi(character, 'implants', f"{base_url.format(char_id=char_id)}/implants/")
        if resp['status'] == 200:
            CharacterImplant.objects.filter(character=character).delete()
            new_implants = [
                CharacterImplant(character=character, type_id=imp_id) 
                for imp_id in resp['data']
            ]
            CharacterImplant.objects.bulk_create(new_implants)

        # --- PUBLIC INFO ---
        resp = call_esi(character, 'public_info', f"{base_url.format(char_id=char_id)}/")
        if resp['status'] == 200:
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
        resp = call_esi(character, 'history', f"{base_url.format(char_id=char_id)}/corporationhistory/")
        if resp['status'] == 200:
            CharacterHistory.objects.filter(character=character).delete()
            history_data = resp['data']
            
            # Batch resolve names
            corp_ids = set(h['corporation_id'] for h in history_data)
            corp_names = {}
            
            if corp_ids:
                name_resp = requests.post("https://esi.evetech.net/latest/universe/names/", json=list(corp_ids))
                if name_resp.status_code == 200:
                    for entry in name_resp.json():
                        corp_names[entry['id']] = entry['name']

            new_history = [
                CharacterHistory(
                    character=character,
                    corporation_id=h['corporation_id'],
                    corporation_name=corp_names.get(h['corporation_id'], f"Unknown ({h['corporation_id']})"),
                    start_date=h['start_date']
                ) for h in history_data
            ]
            CharacterHistory.objects.bulk_create(new_history)

        # CRITICAL FIX: Force update 'last_updated' timestamp even if all calls were 304 (Cached)
        # This prevents the frontend from looping infinitely
        character.save() 

        return True

    except Exception as e:
        print(f"ESI Update Process Error: {e}")
        return False