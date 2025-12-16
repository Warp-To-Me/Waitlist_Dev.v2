import requests
from django.utils import timezone
from dateutil.parser import parse
from django.core.cache import cache
from django.db.models import Q
from pilot_data.models import SRPConfiguration, CorpWalletJournal
from esi_calls.esi_network import call_esi
from esi_calls.token_manager import check_token, force_refresh_token
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
        print(f"[SRP Sync] Starting Division {division}...")
        page = 1
        keep_fetching = True
        consecutive_full_dupe_pages = 0
        div_new_count = 0
        
        while keep_fetching:
            try:
                url = f"{ESI_BASE}/corporations/{corp_id}/wallets/{division}/journal/"
                
                # --- RETRY LOGIC FOR 401 (Invalid Token) ---
                retry_count = 0
                max_retries = 1
                resp = {'status': 0}

                while retry_count <= max_retries:
                    resp = call_esi(character, f'corp_wallet_{corp_id}_{division}_{page}', url, params={'page': page}, force_refresh=True)

                    if resp['status'] == 401:
                        print(f"[SRP Sync] 401 on Div {division}. Forcing Token Refresh...")
                        if force_refresh_token(character):
                            retry_count += 1
                            continue # Retry loop
                        else:
                            break # Refresh failed
                    elif resp['status'] == 403:
                         print(f"[SRP Sync] 403 Forbidden on Div {division}. Missing Scope?")
                         # Do not retry on 403, it won't help
                         break
                    else:
                        break # Not a 401, proceed

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
                    count = len(db_objects)
                    total_new += count
                    div_new_count += count
                
                page += 1
                if page > 50:
                    print(f"[SRP Sync] Div {division} hit page limit (50). Stopping.")
                    keep_fetching = False
            
            except Exception as e:
                print(f"Error syncing Div {division} Page {page}: {e}")
                errors.append(f"Div {division} Crash: {str(e)}")
                keep_fetching = False # Stop this division, but allow loop to continue to next division

        print(f"[SRP Sync] Finished Division {division}. New Entries: {div_new_count}")

    if latest_esi_date:
        srp_config.last_sync = latest_esi_date
    else:
        srp_config.last_sync = timezone.now()

    srp_config.save()
    
    # --- STEP 2: BACKFILL "UNKNOWN" NAMES ---
    # Attempt to repair existing entries with missing names (e.g. if ESI failed previously)
    try:
        unknown_entries = CorpWalletJournal.objects.filter(
            Q(first_party_name__in=['', 'Unknown']) | Q(second_party_name__in=['', 'Unknown']),
            config=srp_config
        ).values_list('entry_id', 'first_party_id', 'second_party_id')[:200] # Limit batch size

        unknown_ids_to_resolve = set()
        entries_to_update = []

        # Check Corp Name logic first
        if corp_id and not character.corporation_name:
             # Force resolve corp if missing name in DB
             unknown_ids_to_resolve.add(corp_id)

        for entry in unknown_entries:
            eid, fid, sid = entry
            if fid: unknown_ids_to_resolve.add(fid)
            if sid: unknown_ids_to_resolve.add(sid)
            entries_to_update.append({'entry_id': eid, 'fid': fid, 'sid': sid})

        if unknown_ids_to_resolve:
            print(f"[SRP Sync] Attempting to backfill names for {len(unknown_ids_to_resolve)} IDs...")
            resolved_map = resolve_unknown_names(list(unknown_ids_to_resolve))

            # Explicit Overrides
            if corp_id and character.corporation_name:
                resolved_map[corp_id] = character.corporation_name
            elif corp_id in resolved_map and not character.corporation_name:
                 # Update char corp name if we resolved it
                 character.corporation_name = resolved_map[corp_id]
                 character.save(update_fields=['corporation_name'])

            if character.character_id:
                resolved_map[character.character_id] = character.character_name

            updated_count = 0
            for item in entries_to_update:
                f_name = resolved_map.get(item['fid'])
                s_name = resolved_map.get(item['sid'])

                if f_name or s_name:
                    update_fields = {}
                    if f_name: update_fields['first_party_name'] = f_name
                    if s_name: update_fields['second_party_name'] = s_name

                    if update_fields:
                        CorpWalletJournal.objects.filter(entry_id=item['entry_id']).update(**update_fields)
                        updated_count += 1

            if updated_count > 0:
                print(f"[SRP Sync] Backfilled names for {updated_count} transactions.")

    except Exception as e:
        print(f"[SRP Sync] Backfill Error: {e}")

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

    cache_key = f"corp_divisions_map_{corp_id}"
    cached = cache.get(cache_key)
    if cached: return cached

    url = f"{ESI_BASE}/corporations/{corp_id}/divisions/"
    
    # --- RETRY LOGIC FOR 401 ---
    retry_count = 0
    max_retries = 1
    resp = {'status': 0}

    while retry_count <= max_retries:
        # Use force_refresh=True to ensure we get body (ignore EsiHeaderCache returning 304)
        resp = call_esi(character, f'corp_divisions_{corp_id}', url, force_refresh=True)

        if resp['status'] == 401:
            if force_refresh_token(character):
                retry_count += 1
                continue
            else:
                break
        elif resp['status'] == 403:
            print(f"[SRP Sync] 403 Forbidden reading Divisions. Missing 'esi-corporations.read_divisions.v1'?")
            break
        else:
            break

    if resp['status'] != 200: return {}
    
    data = resp['data']
    # Map division ID (1-7) to Name
    
    mapping = {}
    if 'wallet' in data:
        for div in data['wallet']:
            div_id = div.get('division')
            if div_id:
                mapping[div_id] = div.get('name', f"Division {div_id}")

    # Cache for 1 hour
    cache.set(cache_key, mapping, timeout=3600)
    return mapping

def get_corp_balances(character):
    """
    Fetches LIVE balances for all divisions directly from ESI.
    Returns: { division_id (int): balance (float) }
    """
    if not check_token(character): return {}
    corp_id = character.corporation_id
    if not corp_id: return {}

    cache_key = f"live_corp_balances_{corp_id}"
    cached = cache.get(cache_key)
    if cached: return cached

    url = f"{ESI_BASE}/corporations/{corp_id}/wallets/"

    # --- RETRY LOGIC FOR 401 ---
    retry_count = 0
    max_retries = 1
    resp = {'status': 0}

    while retry_count <= max_retries:
        # Use force_refresh=True to ensure we get body
        resp = call_esi(character, f'corp_balances_{corp_id}', url, force_refresh=True)

        if resp['status'] == 401:
            if force_refresh_token(character):
                retry_count += 1
                continue
            else:
                break
        elif resp['status'] == 403:
            print(f"[SRP Sync] 403 Forbidden reading Balances. Missing 'esi-wallet.read_corporation_wallets.v1'?")
            break
        else:
            break

    if resp['status'] != 200:
        print(f"[SRP Sync] Failed to fetch balances: {resp.get('status')} {resp.get('error')}")
        return {}

    # ESI Returns: [ {"division": 1, "balance": 100.00}, ... ]
    balances = {}
    for item in resp['data']:
        balances[item['division']] = item['balance']

    # Cache for 60 seconds
    cache.set(cache_key, balances, timeout=60)
    return balances
