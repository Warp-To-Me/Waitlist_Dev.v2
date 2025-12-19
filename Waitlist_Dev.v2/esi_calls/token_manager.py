import requests
import base64
import os
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from datetime import timedelta
from pilot_data.models import EveCharacter, ItemType, CharacterSkill, CharacterQueue, CharacterImplant, CharacterHistory, SkillHistory, EsiHeaderCache
from esi_calls.esi_network import call_esi
from esi_calls.client import get_esi_client
from esi_calls.signals import notify_user_ratelimit
from esi.models import Token
from bravado.exception import HTTPForbidden
import logging

logger = logging.getLogger(__name__)

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

def get_token_for_scopes(character_id, scopes):
    """
    Returns the most recent valid token for a character that possesses ALL the required scopes.
    """
    return Token.objects.filter(character_id=character_id).require_scopes(scopes).order_by('-created').first()

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
            # We don't strictly need a user token for public info, but using one helps with rate limits?
            # ESI Public endpoints can be called without auth.
            # However, our pattern is to use the user's token if available.
            token = Token.objects.filter(character_id=character.character_id).order_by('-created').first()
            if token:
                try:
                    client = get_esi_client(token)
                    op = client.Character.get_characters_character_id(character_id=char_id)
                    op.request_config.also_return_response = True
                    data, incoming_response = op.result(ignore_cache=force_refresh)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    character.corporation_id = data.get('corporation_id')
                    character.alliance_id = data.get('alliance_id')

                    # Resolve Names
                    names_to_resolve = {character.corporation_id}
                    if character.alliance_id: names_to_resolve.add(character.alliance_id)

                    # Filter out None values
                    names_to_resolve = {n for n in names_to_resolve if n is not None}

                    if names_to_resolve:
                        try:
                            # Use the client for name resolution too
                            op_names = client.Universe.post_universe_names(ids=list(names_to_resolve))
                            op_names.request_config.also_return_response = True
                            name_data, _ = op_names.result(ignore_cache=force_refresh)

                            for entry in name_data:
                                # entry is a dict
                                entry_id = entry.get('id')
                                entry_name = entry.get('name')
                                if entry_id == character.corporation_id:
                                    character.corporation_name = entry_name
                                elif entry_id == character.alliance_id:
                                    character.alliance_name = entry_name
                        except Exception as e:
                            logger.error(f"[ESI Library Error] Name Resolution: {e}")

                    if character.corporation_id:
                        character.save(update_fields=['corporation_id', 'alliance_id', 'corporation_name', 'alliance_name'])
                    else:
                        logger.warning(f"Skipping save for {character.character_name}: corporation_id is None")

                except Exception as e:
                    logger.error(f"[ESI Library Error] Public Info Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during Public Info sync")

        # --- SKILLS ---
        if ENDPOINT_SKILLS in target_endpoints:
            token = get_token_for_scopes(character.character_id, ['esi-skills.read_skills.v1'])
            if token:
                try:
                    client = get_esi_client(token)
                    op = client.Skills.get_characters_character_id_skills(character_id=char_id)
                    op.request_config.also_return_response = True
                    data, incoming_response = op.result(ignore_cache=force_refresh)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    character.total_sp = data.get('total_sp', 0)
                    character.save(update_fields=['total_sp'])

                    old_skills_map = {s.skill_id: s for s in CharacterSkill.objects.filter(character=character)}
                    history_buffer = []

                    skills_list = data.get('skills', [])

                    for s_data in skills_list:
                        sid = s_data.get('skill_id')
                        new_level = s_data.get('active_skill_level')
                        new_sp = s_data.get('skillpoints_in_skill')

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
                            character=character, skill_id=s.get('skill_id'),
                            active_skill_level=s.get('active_skill_level'), skillpoints_in_skill=s.get('skillpoints_in_skill')
                        ) for s in skills_list
                    ]
                    CharacterSkill.objects.bulk_create(new_skills)
                except HTTPForbidden:
                    logger.warning(f"Missing Scope 'esi-skills.read_skills.v1' for {character.character_name}")
                except Exception as e:
                    logger.error(f"[ESI Library Error] Skills Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during Skills sync")


        # --- SKILL QUEUE ---
        if ENDPOINT_QUEUE in target_endpoints:
            token = get_token_for_scopes(character.character_id, ['esi-skills.read_skillqueue.v1'])
            if token:
                try:
                    client = get_esi_client(token)
                    op = client.Skills.get_characters_character_id_skillqueue(character_id=char_id)
                    op.request_config.also_return_response = True
                    data, incoming_response = op.result(ignore_cache=force_refresh)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    CharacterQueue.objects.filter(character=character).delete()
                    # data is a list of objects for this endpoint
                    new_queue = [
                        CharacterQueue(
                            character=character, skill_id=item.get('skill_id'),
                            finished_level=item.get('finished_level'), queue_position=item.get('queue_position'),
                            finish_date=item.get('finish_date')
                        ) for item in data
                    ]
                    CharacterQueue.objects.bulk_create(new_queue)
                except HTTPForbidden:
                    logger.warning(f"Missing Scope 'esi-skills.read_skillqueue.v1' for {character.character_name}")
                except Exception as e:
                    logger.error(f"[ESI Library Error] Skill Queue Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during Skill Queue sync")

        # --- SHIP ---
        if ENDPOINT_SHIP in target_endpoints:
            # New Migration to ESI Library
            token = get_token_for_scopes(character.character_id, ['esi-location.read_ship_type.v1'])
            if token:
                try:
                    # get_esi_client handles UA. token.get_esi_client uses factory internally too but we use our helper.
                    client = get_esi_client(token)
                    op = client.Location.get_characters_character_id_ship(character_id=char_id)
                    op.request_config.also_return_response = True
                    data, incoming_response = op.result(ignore_cache=force_refresh)

                    # Notify Rate Limits (Manual Hook)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    character.current_ship_name = data.get('ship_name', 'Unknown')
                    character.current_ship_type_id = data.get('ship_type_id')
                    character.save(update_fields=['current_ship_name', 'current_ship_type_id'])

                except HTTPForbidden:
                    logger.warning(f"Missing Scope 'esi-location.read_ship_type.v1' for {character.character_name}")
                except Exception as e:
                    logger.error(f"[ESI Library Error] Ship Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during Ship sync")

        # --- WALLET BALANCE ---
        if ENDPOINT_WALLET in target_endpoints:
            token = get_token_for_scopes(character.character_id, ['esi-wallet.read_character_wallet.v1'])
            if token:
                try:
                    client = get_esi_client(token)
                    op = client.Wallet.get_characters_character_id_wallet(character_id=char_id)
                    op.request_config.also_return_response = True
                    # Force refresh supported by django-esi if configured
                    data, incoming_response = op.result(ignore_cache=force_refresh)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    character.wallet_balance = data
                    character.save(update_fields=['wallet_balance'])
                except HTTPForbidden:
                    logger.warning(f"Missing Scope 'esi-wallet.read_character_wallet.v1' for {character.character_name}")
                except Exception as e:
                    logger.error(f"[ESI Library Error] Wallet Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during Wallet sync")

        # --- LOYALTY POINTS ---
        if ENDPOINT_LP in target_endpoints:
            token = get_token_for_scopes(character.character_id, ['esi-characters.read_loyalty.v1'])
            if token:
                try:
                    client = get_esi_client(token)
                    op = client.Loyalty.get_characters_character_id_loyalty_points(character_id=char_id)
                    op.request_config.also_return_response = True
                    data, incoming_response = op.result(ignore_cache=force_refresh)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    # data is list of dicts: {'corporation_id': 123, 'loyalty_points': 500}
                    concord_entry = next((item for item in data if item.get('corporation_id') == 1000125), None)
                    character.concord_lp = concord_entry.get('loyalty_points') if concord_entry else 0
                    character.save(update_fields=['concord_lp'])
                except HTTPForbidden:
                    logger.warning(f"Missing Scope 'esi-characters.read_loyalty.v1' for {character.character_name}")
                except Exception as e:
                    logger.error(f"[ESI Library Error] LP Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during LP sync")

        # --- IMPLANTS ---
        if ENDPOINT_IMPLANTS in target_endpoints:
            token = get_token_for_scopes(character.character_id, ['esi-clones.read_implants.v1'])
            if token:
                try:
                    client = get_esi_client(token)
                    op = client.Clones.get_characters_character_id_implants(character_id=char_id)
                    op.request_config.also_return_response = True
                    data, incoming_response = op.result(ignore_cache=force_refresh)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    CharacterImplant.objects.filter(character=character).delete()
                    # data is list of integers (type_ids)
                    new_implants = [CharacterImplant(character=character, type_id=imp_id) for imp_id in data]
                    CharacterImplant.objects.bulk_create(new_implants)
                except HTTPForbidden:
                    logger.warning(f"Missing Scope 'esi-clones.read_implants.v1' for {character.character_name}")
                except Exception as e:
                    logger.error(f"[ESI Library Error] Implants Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during Implants sync")

        # --- HISTORY ---
        if ENDPOINT_HISTORY in target_endpoints:
            token = get_token_for_scopes(character.character_id, ['esi-corporations.read_corporation_membership.v1'])
            if token:
                try:
                    client = get_esi_client(token)
                    op = client.Character.get_characters_character_id_corporationhistory(character_id=char_id)
                    op.request_config.also_return_response = True
                    data, incoming_response = op.result(ignore_cache=force_refresh)
                    notify_user_ratelimit(character.user, incoming_response.headers)

                    CharacterHistory.objects.filter(character=character).delete()

                    history_data = data # list of dicts
                    corp_ids = {h.get('corporation_id') for h in history_data if h.get('corporation_id')}
                    corp_names = {}

                    if corp_ids:
                        try:
                            op_names = client.Universe.post_universe_names(ids=list(corp_ids))
                            op_names.request_config.also_return_response = True
                            name_data, _ = op_names.result(ignore_cache=force_refresh)
                            for entry in name_data:
                                corp_names[entry.get('id')] = entry.get('name')
                        except Exception as e:
                            logger.error(f"[ESI Library Error] History Name Resolution: {e}")

                    new_history = [
                        CharacterHistory(
                            character=character, corporation_id=h.get('corporation_id'),
                            corporation_name=corp_names.get(h.get('corporation_id'), f"Unknown ({h.get('corporation_id')})"),
                            start_date=h.get('start_date')
                        ) for h in history_data
                    ]
                    CharacterHistory.objects.bulk_create(new_history)
                except HTTPForbidden:
                    logger.warning(f"Missing Scope 'esi-corporations.read_corporation_membership.v1' for {character.character_name}")
                except Exception as e:
                    logger.error(f"[ESI Library Error] History Endpoint: {e}")
            else:
                logger.warning(f"No valid token found for character {character.character_name} during History sync")

        character.last_updated = timezone.now()
        character.save(update_fields=['last_updated'])

        return True

    except Exception as e:
        print(f"ESI Update Process Error: {e}")
        return False
