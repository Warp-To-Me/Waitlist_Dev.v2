import requests
import email.utils
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone
from pilot_data.models import EsiHeaderCache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Standard HTTP Date Format for ESI
DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

def get_esi_session():
    """
    Creates a requests session with automatic retries for server errors.
    """
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[502, 503, 504],
        allowed_methods=frozenset(['GET', 'POST'])
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

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
        if timezone.now() < cache_entry.expires:
            print(f"  -> [SKIP] {endpoint_name}: Cached until {cache_entry.expires.strftime('%H:%M:%S')}")
            return {'status': 304, 'data': None}

    # 2. Prepare Request
    headers = {
        'Authorization': f'Bearer {character.access_token}',
        'User-Agent': 'Waitlist-Project-v1 (contact: admin@example.com)', 
        'Accept': 'application/json'
    }
    
    if cache_entry and cache_entry.etag:
        headers['If-None-Match'] = cache_entry.etag

    try:
        print(f"  -> [REQ] {endpoint_name}")
        
        # Use Session with Retry logic
        session = get_esi_session()
        
        if method == 'GET':
            response = session.get(url, headers=headers, params=params, timeout=10)
        else:
            response = session.post(url, headers=headers, json=body, timeout=10)

        # --- RATE LIMIT HANDLING ---
        rem = response.headers.get('X-Ratelimit-Remaining')
        if rem and int(rem) < 20:
            print(f"  !!! WARNING: Rate Limit Low: {rem} !!!")

        # 3. Handle 304 Not Modified
        if response.status_code == 304:
            print(f"  -> [304] {endpoint_name}: Data Unchanged")
            _update_cache_headers(character, endpoint_name, response.headers, cache_entry)
            return {'status': 304, 'data': None}

        # 4. Handle 200 OK
        if response.status_code == 200:
            print(f"  -> [200] {endpoint_name}: New Data")
            _update_cache_headers(character, endpoint_name, response.headers, cache_entry)
            return {'status': 200, 'data': response.json()}
            
        # Handle Token Errors
        if response.status_code in [401, 403]:
            print(f"  -> [{response.status_code}] Token Invalid/Scope Missing")
            return {'status': response.status_code, 'data': None}

        # Handle Server Errors explicitly (though RaiseForStatus catches them too)
        if response.status_code >= 500:
            print(f"  -> [{response.status_code}] ESI Server Error")
            return {'status': response.status_code, 'error': 'Server Error'}

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
            dt_tuple = email.utils.parsedate_tz(expires_str)
            if dt_tuple:
                dt_ts = email.utils.mktime_tz(dt_tuple)
                expires_dt = datetime.fromtimestamp(dt_ts, dt_timezone.utc)
        except ValueError:
            pass

    EsiHeaderCache.objects.update_or_create(
        character=character,
        endpoint_name=endpoint_name,
        defaults={
            'etag': etag.strip('"') if etag else None,
            'expires': expires_dt
        }
    )