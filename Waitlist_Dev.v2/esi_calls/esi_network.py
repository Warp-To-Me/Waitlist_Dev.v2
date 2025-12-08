import requests
import email.utils
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone
from pilot_data.models import EsiHeaderCache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Channels imports for broadcasting
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

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

def _broadcast_ratelimit(user, headers):
    """
    Helper to parse Rate Limit headers and push to the user's websocket.
    """
    if not user or not user.is_authenticated:
        return

    remaining = headers.get('X-Ratelimit-Remaining')
    limit_str = headers.get('X-Ratelimit-Limit')
    bucket_group = headers.get('X-Ratelimit-Group', 'default')
    esi_remain = headers.get('X-Esi-Error-Limit-Remain')
    
    payload = None

    if remaining and limit_str:
        try:
            limit_val, window_str = limit_str.split('/')
            limit_val = int(limit_val)
            payload = {
                'type': 'ratelimit',
                'bucket': bucket_group,
                'remaining': int(remaining),
                'limit': limit_val,
                'window': window_str
            }
        except ValueError:
            pass
            
    elif esi_remain:
        payload = {
            'type': 'ratelimit',
            'bucket': 'Global Error',
            'remaining': int(esi_remain),
            'limit': 100, 
            'window': '60s'
        }

    if payload:
        try:
            channel_layer = get_channel_layer()
            # FIX: Check if we are already in an async loop (e.g. gevent)
            # If so, we can't use AsyncToSync easily. 
            # For now, we wrap it in a try/except to prevent crashing the ESI call.
            # Ideally, we should schedule this on the event loop if one exists.
            
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "user_notification",
                    "data": payload
                }
            )
        except Exception as e:
            # Log specific warning for the loop issue but don't crash
            if "AsyncToSync" in str(e):
                print(f"Warning: Skipping ratelimit broadcast due to async context conflict: {e}")
            else:
                print(f"Error broadcasting ratelimit: {e}")

def call_esi(character, endpoint_name, url, method='GET', params=None, body=None, force_refresh=False):
    """
    Smart ESI Caller.
    :param force_refresh: If True, ignores local DB cache and ETags to ensure data is returned.
    """
    # 1. Check Cache Validity (Unless forced)
    cache_entry = None
    if not force_refresh:
        cache_entry = EsiHeaderCache.objects.filter(character=character, endpoint_name=endpoint_name).first()
        
        if cache_entry and cache_entry.expires:
            if timezone.now() < cache_entry.expires:
                return {'status': 304, 'data': None}

    # 2. Prepare Request
    headers = {
        'Authorization': f'Bearer {character.access_token}',
        'User-Agent': 'Waitlist-Project-v1 (contact: admin@example.com)', 
        'Accept': 'application/json'
    }
    
    # Only send ETag if we are NOT forcing a refresh
    if not force_refresh and cache_entry and cache_entry.etag:
        headers['If-None-Match'] = cache_entry.etag

    try:
        session = get_esi_session()
        
        if method == 'GET':
            response = session.get(url, headers=headers, params=params, timeout=10)
        else:
            response = session.post(url, headers=headers, json=body, timeout=10)

        # --- BROADCAST RATE LIMITS ---
        _broadcast_ratelimit(character.user, response.headers)

        # --- RATE LIMIT WARNING ---
        rem = response.headers.get('X-Ratelimit-Remaining')
        if rem and int(rem) < 20:
            print(f"  !!! WARNING: Rate Limit Low: {rem} !!!")

        # 3. Handle 304 Not Modified
        if response.status_code == 304:
            _update_cache_headers(character, endpoint_name, response.headers, cache_entry)
            return {'status': 304, 'data': None}

        # 4. Handle 200 OK
        if response.status_code == 200:
            _update_cache_headers(character, endpoint_name, response.headers, cache_entry)
            return {'status': 200, 'data': response.json()}
            
        # Handle Token Errors
        if response.status_code in [401, 403]:
            print(f"  -> [{response.status_code}] Token Invalid/Scope Missing")
            return {'status': response.status_code, 'data': None}

        # Handle Server Errors
        if response.status_code >= 500:
            print(f"  -> [{response.status_code}] ESI Server Error")
            return {'status': response.status_code, 'error': 'Server Error'}

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