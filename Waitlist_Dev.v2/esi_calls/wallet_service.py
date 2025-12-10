import requests
from django.utils import timezone
from dateutil.parser import parse
from pilot_data.models import SRPConfiguration, CorpWalletJournal
from esi_calls.esi_network import call_esi
from esi_calls.token_manager import check_token
from esi_calls.fleet_service import resolve_unknown_names

ESI_BASE = "https://esi.evetech.net/latest"

def sync_corp_wallet(srp_config):
    """
    Fetches wallet journal for the configured corp/character.
    Iterates pages until existing data is found.
    """
    character = srp_config.character
    if not check_token(character):
        return False, "Token Invalid"

    corp_id = character.corporation_id
    if not corp_id:
        return False, "Character has no corporation"

    # We assume Division 1 (Master) for now, but really we should loop all divisions
    # EVE has 7 divisions. 
    total_new = 0
    errors = []

    # Iterate divisions 1 through 7
    for division in range(1, 8):
        page = 1
        keep_fetching = True
        
        while keep_fetching:
            url = f"{ESI_BASE}/corporations/{corp_id}/wallets/{division}/journal/"
            resp = call_esi(character, f'corp_wallet_{corp_id}_{division}_{page}', url, params={'page': page}, force_refresh=True)
            
            if resp['status'] != 200:
                if resp['status'] != 404: # 404 just means no more pages usually
                    errors.append(f"Div {division} Page {page}: {resp.get('error')}")
                keep_fetching = False
                continue

            data = resp['data']
            if not data:
                keep_fetching = False
                continue

            # Process Entries
            new_entries = []
            party_ids_to_resolve = set()

            existing_ids = set(CorpWalletJournal.objects.filter(
                config=srp_config, 
                entry_id__in=[x['id'] for x in data]
            ).values_list('entry_id', flat=True))

            for row in data:
                if row['id'] in existing_ids:
                    # If we hit existing data, we can stop fetching deeper pages for this division
                    keep_fetching = False 
                    continue

                if row.get('first_party_id'): party_ids_to_resolve.add(row['first_party_id'])
                if row.get('second_party_id'): party_ids_to_resolve.add(row['second_party_id'])

                new_entries.append(row)

            # Resolve Names
            names_map = resolve_unknown_names(list(party_ids_to_resolve))

            # Create Objects
            db_objects = []
            for row in new_entries:
                db_objects.append(CorpWalletJournal(
                    config=srp_config,
                    entry_id=row['id'],
                    amount=row.get('amount', 0),
                    balance=row.get('balance', 0),
                    context_id=row.get('context_id'),
                    context_id_type=row.get('context_id_type'),
                    date=parse(row['date']),
                    description=row.get('description', ''),
                    first_party_id=row.get('first_party_id'),
                    second_party_id=row.get('second_party_id'),
                    reason=row.get('reason', ''),
                    ref_type=row.get('ref_type', ''),
                    tax=row.get('tax'),
                    division=division,
                    first_party_name=names_map.get(row.get('first_party_id'), ''),
                    second_party_name=names_map.get(row.get('second_party_id'), '')
                ))

            if db_objects:
                CorpWalletJournal.objects.bulk_create(db_objects, ignore_conflicts=True)
                total_new += len(db_objects)
            
            page += 1
            if page > 20: keep_fetching = False # Safety break

    srp_config.last_sync = timezone.now()
    srp_config.save()
    
    if errors:
        return False, "; ".join(errors)
    
    return True, f"Synced {total_new} entries."