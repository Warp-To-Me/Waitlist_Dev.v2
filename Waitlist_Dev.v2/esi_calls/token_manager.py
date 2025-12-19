import requests
import base64
import os
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
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
SKIP_IF_OFFLINE = [ENDPOINT_SHIP, ENDPOINT_IMPLANTS]

def check_esi_status():
    """
    Checks EVE Online server status via ESI.
    Returns True if online and accepting requests.
    Caches result for 60 seconds to prevent spamming the status endpoint.
    """
    # 1. Check Cache
    status = cache.get('esi_status_flag')
    if status is not None:
        return status

    # 2. Check Endpoint
    url = "https://esi.evetech.net/latest/status/"
    try:
        # Use standard requests (no auth needed) with short timeout
        resp = requests.get(url, timeout=3)
        
        if resp.status_code == 200:
            data = resp.json()
            # If VIP is True, the server is in restricted mode (usually dev only or startup)
            if data.get('vip') is True:
                print("  [ESI Status] VIP Mode Enabled. Halting calls.")
                is_healthy = False
            else:
                is_healthy = True
        else:
            print(f"  [ESI Status] Endpoint returned {resp.status_code}. Halting calls.")
            is_healthy = False
            
    except Exception as e:
        print(f"  [ESI Status] Connection failed: {e}")
        is_healthy = False

    # 3. Set Cache (Short TTL)
    cache.set('esi_status_flag', is_healthy, timeout=60)
    return is_healthy

# REFACTORED: Removed old manual token checks. 
# Token refresh is now handled automatically by call_esi() via django-esi.

# UPDATED: Added force_refresh parameter
def update_character_data(character, target_endpoints=None, force_refresh=False):
    """
    Updates character data from ESI.
    """
    # 1. Global Circuit Breaker (Check Status First)
    if not check_esi_status():
        return False
        
    # Old logic called check_token() here. 
    # New logic relies on call_esi() to handle token retrieval and refresh.

    base_url = "https://esi.evetech.net/latest/characters/{char_id}"
    char_id = character.character_id

    if target_endpoints is None:
        target_endpoints = list(ALL_ENDPOINTS)

    try:
        # --- NEW: Error Handler with Backoff ---
        def check_critical_error(response, endpoint_name):
            if response['status'] >= 500:
                print(f"  !!! CRITICAL ESI ERROR {response['status']} ({endpoint_name}). Backing off.")
                
                # UPDATE: Apply a 2-minute cooldown to this endpoint's cache
                # This prevents the Dispatcher from picking it up again immediately
                defaults = {'expires': timezone.now() + timedelta(minutes=2)}
                
                rows_updated = EsiHeaderCache.objects.filter(character=character, endpoint_name=endpoint_name).update(**defaults)
                
                if rows_updated == 0:
                    try:
                        EsiHeaderCache.objects.create(character=character, endpoint_name=endpoint_name, **defaults)
                    except Exception:
                        pass
                        
                return True
            return False

        # --- ONLINE STATUS ---
        if ENDPOINT_ONLINE in target_endpoints:
            # Pass force_refresh
            resp = call_esi(character, ENDPOINT_ONLINE, f"{base_url.format(char_id=char_id)}/online/", force_refresh=force_refresh)
            
            if resp['status'] == 403:
                print(f"  !!! Missing Scope 'esi-location.read_online.v1' for {character.character_name}")
            elif not check_critical_error(resp, ENDPOINT_ONLINE) and resp['status'] == 200:
                data = resp['data']
                character.is_online = data.get('online', False)
                character.last_login_at = data.get('last_login')
                character.save(update_fields=['is_online', 'last_login_at'])

                if not character.is_online:
                    for ep in SKIP_IF_OFFLINE:
                        if ep in target_endpoints:
                            target_endpoints.remove(ep)
                            
                            defaults = {'expires': timezone.now()}
                            rows_updated = EsiHeaderCache.objects.filter(character=character, endpoint_name=ep).update(**defaults)
                            if rows_updated == 0:
                                try:
                                    EsiHeaderCache.objects.create(character=character, endpoint_name=ep, **defaults)
                                except Exception:
                                    pass

        # --- PUBLIC INFO (Corp/Alliance) ---
        if ENDPOINT_PUBLIC_INFO in target_endpoints:
            resp = call_esi(character, ENDPOINT_PUBLIC_INFO, f"{base_url.format(char_id=char_id)}/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_PUBLIC_INFO) and resp['status'] == 200:
                data = resp['data']
                character.corporation_id = data.get('corporation_id')
                character.alliance_id = data.get('alliance_id')
                
                names_to_resolve = {character.corporation_id}
                if character.alliance_id: names_to_resolve.add(character.alliance_id)
                
                try:
                    name_resp = requests.post("https://esi.evetech.net/latest/universe/names/", json=list(names_to_resolve))
                    if name_resp.status_code == 200:
                        for entry in name_resp.json():
                            if entry['id'] == character.corporation_id:
                                character.corporation_name = entry['name']
                            elif entry['id'] == character.alliance_id:
                                character.alliance_name = entry['name']
                except Exception as e:
                    print(f"Error resolving names: {e}")
                
                character.save(update_fields=['corporation_id', 'alliance_id', 'corporation_name', 'alliance_name'])

        # --- SKILLS ---
        if ENDPOINT_SKILLS in target_endpoints:
            resp = call_esi(character, ENDPOINT_SKILLS, f"{base_url.format(char_id=char_id)}/skills/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_SKILLS) and resp['status'] == 200:
                data = resp['data']
                character.total_sp = data.get('total_sp', 0)
                character.save(update_fields=['total_sp'])
                
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
            resp = call_esi(character, ENDPOINT_QUEUE, f"{base_url.format(char_id=char_id)}/skillqueue/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_QUEUE) and resp['status'] == 200:
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
            resp = call_esi(character, ENDPOINT_SHIP, f"{base_url.format(char_id=char_id)}/ship/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_SHIP) and resp['status'] == 200:
                data = resp['data']
                character.current_ship_name = data.get('ship_name', 'Unknown')
                character.current_ship_type_id = data.get('ship_type_id')
                character.save(update_fields=['current_ship_name', 'current_ship_type_id'])

        # --- WALLET BALANCE ---
        if ENDPOINT_WALLET in target_endpoints:
            resp = call_esi(character, ENDPOINT_WALLET, f"{base_url.format(char_id=char_id)}/wallet/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_WALLET):
                if resp['status'] == 200:
                    character.wallet_balance = resp['data']
                    character.save(update_fields=['wallet_balance'])
                elif resp['status'] == 403:
                    print(f"  !!! Missing Scopes for Wallet: {character.character_name}")

        # --- LOYALTY POINTS ---
        if ENDPOINT_LP in target_endpoints:
            resp = call_esi(character, ENDPOINT_LP, f"{base_url.format(char_id=char_id)}/loyalty/points/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_LP):
                if resp['status'] == 200:
                    concord_entry = next((item for item in resp['data'] if item['corporation_id'] == 1000125), None)
                    character.concord_lp = concord_entry['loyalty_points'] if concord_entry else 0
                    character.save(update_fields=['concord_lp'])
                elif resp['status'] == 403:
                    print(f"  !!! Missing Scopes for LP: {character.character_name}")

        # --- IMPLANTS ---
        if ENDPOINT_IMPLANTS in target_endpoints:
            resp = call_esi(character, ENDPOINT_IMPLANTS, f"{base_url.format(char_id=char_id)}/implants/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_IMPLANTS) and resp['status'] == 200:
                CharacterImplant.objects.filter(character=character).delete()
                new_implants = [CharacterImplant(character=character, type_id=imp_id) for imp_id in resp['data']]
                CharacterImplant.objects.bulk_create(new_implants)

        # --- HISTORY ---
        if ENDPOINT_HISTORY in target_endpoints:
            resp = call_esi(character, ENDPOINT_HISTORY, f"{base_url.format(char_id=char_id)}/corporationhistory/", force_refresh=force_refresh)
            if not check_critical_error(resp, ENDPOINT_HISTORY) and resp['status'] == 200:
                CharacterHistory.objects.filter(character=character).delete()
                history_data = resp['data']
                corp_ids = set(h['corporation_id'] for h in history_data)
                corp_names = {}
                if corp_ids:
                    try:
                        name_resp = requests.post("https://esi.evetech.net/latest/universe/names/", json=list(corp_ids))
                        if name_resp.status_code == 200:
                            for entry in name_resp.json():
                                corp_names[entry['id']] = entry['name']
                    except Exception as e:
                        print(f"Error resolving history names: {e}")
                        
                new_history = [
                    CharacterHistory(
                        character=character, corporation_id=h['corporation_id'],
                        corporation_name=corp_names.get(h['corporation_id'], f"Unknown ({h['corporation_id']})"),
                        start_date=h['start_date']
                    ) for h in history_data
                ]
                CharacterHistory.objects.bulk_create(new_history)

        character.last_updated = timezone.now()
        character.save(update_fields=['last_updated'])

        return True

    except Exception as e:
        print(f"ESI Update Process Error: {e}")
        return False
