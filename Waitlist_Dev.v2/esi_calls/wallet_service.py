import requests
from django.utils import timezone
from dateutil.parser import parse
from pilot_data.models import SRPConfiguration, CorpWalletJournal
from esi_calls.esi_network import call_esi
from esi_calls.token_manager import check_token
from esi_calls.fleet_service import resolve_unknown_names

ESI_BASE = "https://esi.evetech.net/latest"

def determine_auto_category(amount, reason, first_party_id, second_party_id, corp_id, ref_type=None):
    """
    Applies business rules to guess the category.
    Shared by Sync and Backfill tools.
    """
    reason = str(reason or "").lower() # Normalize to lowercase string
    
    # 1. Tax / Broker Fees (Check ref_type first as it is most reliable)
    if ref_type:
        # Standard ESI ref_types for taxes and fees
        if ref_type in ['contract_brokers_fee', 'brokers_fee', 'transaction_tax', 'tax']:
            return 'tax'

    # Fallback text check for broker fees if ref_type wasn't definitive
    if "broker's fee" in reason or "brokers fee" in reason:
        return 'tax'

    # 2. Internal Transfer (Corp to Corp)
    if first_party_id == corp_id and second_party_id == corp_id:
        return 'internal_transfer'

    # 3. SRP In (Positive Amount)
    if amount > 0:
        if "srp" in reason:
            return 'srp_in'
        # Multiple of 20,000,000 (Insurance Payouts often look like this or user donations)
        try:
            # Use small epsilon for float comparison just in case
            if abs(float(amount) % 20000000) < 0.1:
                return 'srp_in'
        except:
            pass

    # 4. SRP Out (Negative Amount)
    if amount < 0:
        if "srp" in reason:
            return 'srp_out'
        if "giveaway" in reason:
            return 'giveaway'

    return None

def sync_corp_wallet(srp_config):
    """
    Fetches wallet journal for the configured corp/character.
    Designed to be APPEND-ONLY to preserve history beyond ESI's 30-day limit.
    """
    character = srp_config.character
    if not check_token(character):
        return False, "Token Invalid"

    corp_id = character.corporation_id
    if not corp_id:
        return False, "Character has no corporation"

    total_new = 0
    errors = []

    # Store the latest ESI date header encountered
    latest_esi_date = None

    # Iterate divisions 1 through 7
    for division in range(1, 8):
        page = 1
        keep_fetching = True
        consecutive_full_dupe_pages = 0
        
        while keep_fetching:
            try:
                url = f"{ESI_BASE}/corporations/{corp_id}/wallets/{division}/journal/"
                resp = call_esi(character, f'corp_wallet_{corp_id}_{division}_{page}', url, params={'page': page}, force_refresh=True)

                if resp['status'] != 200:
                    if resp['status'] != 404:
                        errors.append(f"Div {division} Page {page}: {resp.get('error')}")
                    keep_fetching = False
                    continue

                # Capture Date Header for Sync Timestamp
                if 'headers' in resp:
                    date_header = resp['headers'].get('Date')
                    if date_header:
                        try:
                            latest_esi_date = parse(date_header)
                        except (ValueError, TypeError) as e:
                            # Log error if date parsing fails but continue
                            print(f"Warning: Failed to parse Date header '{date_header}': {e}")

                data = resp['data']
                if not data:
                    keep_fetching = False
                    continue

                batch_ids = [x['id'] for x in data]
                existing_ids = set(CorpWalletJournal.objects.filter(
                    config=srp_config,
                    entry_id__in=batch_ids
                ).values_list('entry_id', flat=True))

                if len(existing_ids) == len(batch_ids):
                    consecutive_full_dupe_pages += 1
                    if consecutive_full_dupe_pages >= 2:
                        keep_fetching = False
                        continue
                else:
                    consecutive_full_dupe_pages = 0

                new_entries = []
                party_ids_to_resolve = set()

                for row in data:
                    if row['id'] in existing_ids:
                        continue

                    if row.get('first_party_id'): party_ids_to_resolve.add(row['first_party_id'])
                    if row.get('second_party_id'): party_ids_to_resolve.add(row['second_party_id'])

                    new_entries.append(row)

                names_map = resolve_unknown_names(list(party_ids_to_resolve))

                # Add Corp Name and Own Character Name explicitly
                if corp_id and character.corporation_name:
                    names_map[corp_id] = character.corporation_name
                if character.character_id:
                    names_map[character.character_id] = character.character_name

                db_objects = []
                for row in new_entries:
                    amount = float(row.get('amount', 0))
                    reason = row.get('reason', '')
                    f_id = row.get('first_party_id')
                    s_id = row.get('second_party_id')
                    ref_type = row.get('ref_type', '')

                    # Using shared logic
                    auto_cat = determine_auto_category(amount, reason, f_id, s_id, corp_id, ref_type)

                    db_objects.append(CorpWalletJournal(
                        config=srp_config,
                        entry_id=row['id'],
                        amount=amount,
                        balance=row.get('balance', 0),
                        context_id=row.get('context_id'),
                        context_id_type=row.get('context_id_type'),
                        date=parse(row['date']),
                        description=row.get('description', ''),
                        first_party_id=f_id,
                        second_party_id=s_id,
                        reason=reason,
                        ref_type=ref_type,
                        tax=row.get('tax'),
                        division=division,
                        first_party_name=names_map.get(f_id, ''),
                        second_party_name=names_map.get(s_id, ''),
                        custom_category=auto_cat
                    ))

                if db_objects:
                    CorpWalletJournal.objects.bulk_create(db_objects, ignore_conflicts=True)
                    total_new += len(db_objects)

                page += 1
                if page > 50: keep_fetching = False
            
            except Exception as e:
                print(f"Error syncing Div {division} Page {page}: {e}")
                errors.append(f"Div {division} Crash: {str(e)}")
                keep_fetching = False # Stop this division, but allow loop to continue to next division

    if latest_esi_date:
        srp_config.last_sync = latest_esi_date
    else:
        srp_config.last_sync = timezone.now()

    srp_config.save()
    
    if errors:
        return False, "; ".join(errors)
    
    return True, f"Synced {total_new} entries."

def get_corp_divisions(character):
    """
    Fetches Division Names from ESI.
    """
    if not check_token(character): return {}
    corp_id = character.corporation_id
    if not corp_id: return {}

    url = f"{ESI_BASE}/corporations/{corp_id}/divisions/"
    resp = call_esi(character, f'corp_divisions_{corp_id}', url) # Default cache

    if resp['status'] != 200: return {}

    data = resp['data']
    # Map division ID (1-7) to Name
    # ESI returns: { "wallet": [ { "division": 1, "name": "Master Wallet" } ... ] }

    mapping = {}
    if 'wallet' in data:
        for div in data['wallet']:
            mapping[div['division']] = div['name']

    return mapping