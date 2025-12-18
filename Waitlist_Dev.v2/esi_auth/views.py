import requests
import urllib.parse
import os
import secrets
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User, Group
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test  # Added user_passes_test
from django.utils import timezone
from datetime import timedelta

# Import InvalidToken to catch decryption errors
from cryptography.fernet import InvalidToken
import json
import base64

from pilot_data.models import EveCharacter
from scheduler.tasks import refresh_character_task
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

# --- PERMISSION HELPER ---
def can_manage_srp(user):
    # Matches logic in core.views_srp
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='manage_srp_source').exists()

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def auth_login_options(request):
    """
    API Endpoint for Custom Scope Selection Login.
    GET: Returns available scopes and descriptions.
    POST: Accepts list of requested scopes, validates them, and returns SSO URL.
    """
    
    # Define Available Scopes
    base_scopes = settings.EVE_SCOPES_BASE.split()
    optional_scopes = settings.EVE_SCOPES_OPTIONAL.split()
    fc_scopes = settings.EVE_SCOPES_FC.split()
    srp_scopes = settings.EVE_SCOPES_SRP.split()
    
    # Only show FC/SRP scopes if user is authenticated and has permission?
    # But for initial login, we might want to just show Base + Optional.
    # If they are adding an alt, we might show more.
    # For simplicity, we expose Base + Optional to everyone.
    # Advanced scopes (FC/SRP) are usually handled by specific internal flows or can be added here if needed.
    
    # We will combine Optional + FC into the "Optional" list for the UI, 
    # but maybe we should flag them. For now, let's just use Base + Optional.
    # If a user IS an FC, they should probably use the "Login as FC" button or we add FC scopes to optional list.
    
    all_optional = optional_scopes + fc_scopes # Allow users to opt-in to FC scopes if they want
    
    if request.method == 'GET':
        scope_options = []
        for scope in all_optional:
            meta = settings.SCOPE_DESCRIPTIONS.get(scope, {'label': scope, 'description': ''})
            scope_options.append({
                'scope': scope,
                'label': meta['label'],
                'description': meta['description']
            })
            
        base_options = []
        for scope in base_scopes:
             meta = settings.SCOPE_DESCRIPTIONS.get(scope, {'label': scope, 'description': ''})
             base_options.append({
                'scope': scope,
                'label': meta['label'],
                'description': meta['description']
            })

        return JsonResponse({
            'base_scopes': base_options,
            'optional_scopes': scope_options
        })

    if request.method == 'POST':
        data = request.data
        requested_custom = data.get('scopes', [])
        mode = data.get('mode', None)

        # Set session flags based on mode
        _clear_session_flags(request)
        if mode == 'add_alt':
            if not request.user.is_authenticated:
                return HttpResponse("Authentication required to add alt", status=403)
            request.session['is_adding_alt'] = True
        
        elif mode == 'srp_auth':
            if not request.user.is_authenticated or not can_manage_srp(request.user):
                 return HttpResponse("Permission denied for SRP auth", status=403)
            request.session['is_adding_alt'] = True
            request.session['is_srp_auth'] = True

        # Always include Base Scopes
        final_scopes = set(base_scopes)
        
        # Add valid custom scopes
        allowed_optional = set(all_optional)
        for s in requested_custom:
            if s in allowed_optional:
                final_scopes.add(s)

        # If SRP Auth mode, enforce SRP scopes
        if mode == 'srp_auth':
             for s in srp_scopes:
                 final_scopes.add(s)
                
        # Generate State
        state_token = secrets.token_urlsafe(32)
        request.session['sso_state'] = state_token
        
        # Build URL
        scope_str = " ".join(final_scopes)
        params = {
            'response_type': 'code',
            'redirect_uri': settings.EVE_CALLBACK_URL,
            'client_id': settings.EVE_CLIENT_ID,
            'scope': scope_str,
            'state': state_token 
        }
        base_url = "https://login.eveonline.com/v2/oauth/authorize/"
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        return JsonResponse({'redirect_url': url})

def sso_login(request):
    _clear_session_flags(request)
    return _start_sso_flow(request)

@login_required
def add_alt(request):
    _clear_session_flags(request)
    request.session['is_adding_alt'] = True
    return _start_sso_flow(request)

@login_required
@user_passes_test(can_manage_srp)  # <--- SECURITY FIX APPLIED
def srp_auth(request):
    """
    Initiates SSO flow with high-level SRP scopes (Wallet Read).
    Restricted to Admins/Leadership.
    """
    _clear_session_flags(request)
    request.session['is_adding_alt'] = True
    request.session['is_srp_auth'] = True
    return _start_sso_flow(request)

def _clear_session_flags(request):
    """Helper to wipe auth-flow session keys"""
    keys = ['is_adding_alt', 'is_srp_auth', 'sso_state']
    for k in keys:
        if k in request.session:
            del request.session[k]

def _start_sso_flow(request):
    # Generate random state
    state_token = secrets.token_urlsafe(32)
    request.session['sso_state'] = state_token

    # Determine Scopes
    if request.session.get('is_srp_auth'):
        # Request FULL master list (Base + FC + SRP) defined in settings
        scopes = getattr(settings, 'EVE_SCOPES', settings.EVE_SCOPES_BASE)
    else:
        # Standard Logic
        scopes = settings.EVE_SCOPES_BASE
        if request.user.is_authenticated:
            is_fc = request.user.is_superuser or \
                    request.user.groups.filter(capabilities__slug='access_fleet_command').exists()
            
            if is_fc:
                scopes = f"{scopes} {settings.EVE_SCOPES_FC}"

    params = {
        'response_type': 'code',
        'redirect_uri': settings.EVE_CALLBACK_URL,
        'client_id': settings.EVE_CLIENT_ID,
        'scope': scopes,
        'state': state_token 
    }
    base_url = "https://login.eveonline.com/v2/oauth/authorize/"
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)

def sso_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')

    # Retrieve flags BEFORE cleanup
    saved_state = request.session.get('sso_state')
    is_adding = request.session.get('is_adding_alt')
    is_srp = request.session.get('is_srp_auth')
    
    # Now clear flags
    _clear_session_flags(request)
    
    if not state or state != saved_state:
        # Log error or handle state mismatch
        pass 

    if not code: return HttpResponse("SSO Error: No code received", status=400)

    # 1. Exchange code for tokens
    token_url = "https://login.eveonline.com/v2/oauth/token"
    client_id = settings.EVE_CLIENT_ID
    secret_key = os.getenv('EVE_SECRET_KEY')

    try:
        auth_response = requests.post(
            token_url,
            data={'grant_type': 'authorization_code', 'code': code},
            auth=(client_id, secret_key)
        )
        auth_response.raise_for_status()
    except Exception as e:
        return HttpResponse(f"Token Exchange Failed: {e}", status=400)
    
    tokens = auth_response.json()
    access_token = tokens['access_token']
    refresh_token = tokens['refresh_token']
    expires_in = tokens['expires_in']
    token_expiry = timezone.now() + timedelta(seconds=expires_in)

    # 2. Verify Identity
    verify_url = "https://esi.evetech.net/verify/"
    headers = {'Authorization': f'Bearer {access_token}'}
    verify_response = requests.get(verify_url, headers=headers)
    if verify_response.status_code != 200: return HttpResponse("Verification Failed", status=400)
        
    char_data = verify_response.json()
    char_id = char_data['CharacterID']
    char_name = char_data['CharacterName']

    # --- SCOPE EXTRACTION ---
    # Parse JWT to get actual granted scopes
    granted_scopes_str = ""
    try:
        parts = access_token.split('.')
        if len(parts) == 3:
            payload_part = parts[1]
            padding = '=' * (4 - len(payload_part) % 4)
            payload_str = base64.urlsafe_b64decode(payload_part + padding).decode('utf-8')
            payload = json.loads(payload_str)
            
            token_scopes = payload.get('scp', [])
            if isinstance(token_scopes, str):
                token_scopes = [token_scopes]
            
            granted_scopes_str = " ".join(token_scopes)
    except Exception as e:
        print(f"Error parsing token scopes: {e}")
    # ------------------------

    # 3. Handle Linking vs Login
    target_char = None
    
    if request.user.is_authenticated and is_adding:
        # --- ADDING / UPDATING ALT ---
        user = request.user
        
        defaults = {
            'user': user,
            'character_name': char_name,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires': token_expiry,
            'granted_scopes': granted_scopes_str
        }

        if user.characters.filter(is_main=True).exclude(character_id=char_id).exists():
            defaults['is_main'] = False

        try:
            target_char, created = EveCharacter.objects.update_or_create(
                character_id=char_id,
                defaults=defaults
            )
        except InvalidToken:
            EveCharacter.objects.filter(character_id=char_id).update(access_token="", refresh_token="")
            target_char, created = EveCharacter.objects.update_or_create(
                character_id=char_id,
                defaults=defaults
            )

        refresh_character_task.delay(target_char.character_id)
        
        # Redirect Logic
        if is_srp:
            return redirect('/management/srp/config')
        return redirect('/profile')
    else:
        # --- LOGIN ---
        try:
            target_char = EveCharacter.objects.get(character_id=char_id)
        except InvalidToken:
            EveCharacter.objects.filter(character_id=char_id).update(access_token="", refresh_token="")
            target_char = EveCharacter.objects.get(character_id=char_id)
        except EveCharacter.DoesNotExist:
            target_char = None

        if target_char:
            user = target_char.user
            target_char.access_token = access_token
            target_char.refresh_token = refresh_token
            target_char.token_expires = token_expiry
            target_char.granted_scopes = granted_scopes_str
            target_char.save()
        else:
            is_first_user = User.objects.count() == 0
            user = User.objects.create_user(username=str(char_id), first_name=char_name)
            
            if is_first_user:
                user.is_superuser = True
                user.is_staff = True
                user.save()

            default_group, _ = Group.objects.get_or_create(name='Public')
            user.groups.add(default_group)
            
            target_char = EveCharacter.objects.create(
                user=user,
                character_id=char_id,
                character_name=char_name,
                is_main=True,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires=token_expiry,
                granted_scopes=granted_scopes_str
            )
            refresh_character_task.delay(target_char.character_id)

        login(request, user)
        request.session['active_char_id'] = char_id
        return redirect('/')

def logout_view(request):
    logout(request)
    return redirect('/')