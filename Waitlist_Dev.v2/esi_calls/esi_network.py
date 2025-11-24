import requests
import email.utils
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone # Fix: Import standard timezone as dt_timezone
from pilot_data.models import EsiHeaderCache

# Standard HTTP Date Format for ESI
DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

def call_esi(character, endpoint_name, url, method='GET', params=None, body=None):
    """
    Smart ESI Caller.
    1. Checks DB for 'Expires' header. If current time < Expires, SKIPS request (Returns None).
    2. Checks DB for 'ETag'. Adds 'If-None-Match' header.
    3. If 304 Not Modified, returns None (Data unchanged).
    4. If 200 OK, returns JSON and updates DB with new ETag/Expires.
    """
    # 1. Check Cache Validity
    cache_entry = EsiHeaderCache.objects.filter(character=character, endpoint_name=endpoint_name).first()
    
    if cache_entry and cache_entry.expires:
        # django.utils.timezone.now() is still correct here
        if timezone.now() < cache_entry.expires:
            print(f"  -> [SKIP] {endpoint_name}: Cached until {cache_entry.expires.strftime('%H:%M:%S')}")
            return {'status': 304, 'data': None} # Simulated 304 (Local Cache Hit)

    # 2. Prepare Request
    headers = {
        'Authorization': f'Bearer {character.access_token}',
        'User-Agent': 'Waitlist-Project-v1 (contact: admin@example.com)', 
        'Accept': 'application/json'
    }
    
    # Add ETag if we have one (for server-side 304 check)
    if cache_entry and cache_entry.etag:
        headers['If-None-Match'] = cache_entry.etag

    try:
        print(f"  -> [REQ] {endpoint_name}")
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        else:
            response = requests.post(url, headers=headers, json=body)

        # --- RATE LIMIT HANDLING (Logging only for now) ---
        # X-Ratelimit-Remaining: 150
        # X-Ratelimit-Reset: 5 (seconds)
        rem = response.headers.get('X-Ratelimit-Remaining')
        if rem and int(rem) < 20:
            print(f"  !!! WARNING: Rate Limit Low: {rem} !!!")
            # Ideally, we could sleep here or raise an exception to back off

        # 3. Handle 304 Not Modified (Server says: "Your data is still good")
        if response.status_code == 304:
            print(f"  -> [304] {endpoint_name}: Data Unchanged")
            # Even on 304, ESI sends a new Expires header usually. Update it.
            _update_cache_headers(character, endpoint_name, response.headers, cache_entry)
            return {'status': 304, 'data': None}

        # 4. Handle 200 OK (New Data)
        if response.status_code == 200:
            print(f"  -> [200] {endpoint_name}: New Data")
            _update_cache_headers(character, endpoint_name, response.headers, cache_entry)
            return {'status': 200, 'data': response.json()}
            
        # Handle Token Errors (401/403) explicitly
        if response.status_code in [401, 403]:
            print(f"  -> [{response.status_code}] Token Invalid")
            return {'status': response.status_code, 'data': None}

        # Other Errors
        response.raise_for_status()

    except Exception as e:
        print(f"ESI Network Error ({endpoint_name}): {e}")
        return {'status': 500, 'error': str(e)}

    return {'status': 500, 'error': 'Unknown'}

def _update_cache_headers(character, endpoint_name, headers, existing_entry=None):
    """
    Parses ETag and Expires from response and saves to DB.
    """
    etag = headers.get('ETag')
    expires_str = headers.get('Expires')
    expires_dt = None

    if expires_str:
        try:
            # Parse GMT date string to datetime
            # E.g., "Sat, 01 Jan 2022 00:00:00 GMT"
            dt_tuple = email.utils.parsedate_tz(expires_str)
            if dt_tuple:
                dt_ts = email.utils.mktime_tz(dt_tuple)
                # Fix: Use dt_timezone.utc (Standard Lib) instead of timezone.utc (Django)
                expires_dt = datetime.fromtimestamp(dt_ts, dt_timezone.utc)
        except ValueError:
            pass

    # Update or Create
    EsiHeaderCache.objects.update_or_create(
        character=character,
        endpoint_name=endpoint_name,
        defaults={
            'etag': etag.strip('"') if etag else None, # ESI often quotes ETags
            'expires': expires_dt
        }
    )