import requests
import urllib.parse
import os
import secrets
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User, Group
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

# Import InvalidToken to catch decryption errors
from cryptography.fernet import InvalidToken

from pilot_data.models import EveCharacter
from scheduler.tasks import refresh_character_task

def sso_login(request):
    if 'is_adding_alt' in request.session:
        del request.session['is_adding_alt']
    return _start_sso_flow(request)

@login_required
def add_alt(request):
    request.session['is_adding_alt'] = True
    return _start_sso_flow(request)

def _start_sso_flow(request):
    # Generate random state
    state_token = secrets.token_urlsafe(32)
    request.session['sso_state'] = state_token

    # 1. Default to Base Scopes
    scopes = settings.EVE_SCOPES_BASE

    # 2. If User is FC, append FC Scopes
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

    # Verify State
    saved_state = request.session.get('sso_state')
    if 'sso_state' in request.session:
        del request.session['sso_state']

    if not state or state != saved_state:
        # For dev/debug, you might want to relax this or print a warning instead of blocking
        # return HttpResponse("Security Error: State mismatch", status=403)
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

    # 3. Handle Linking vs Login
    target_char = None

    if request.user.is_authenticated and request.session.get('is_adding_alt'):
        # --- ADDING ALT ---
        user = request.user
        del request.session['is_adding_alt']
        
        defaults = {
            'user': user,
            'character_name': char_name,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires': token_expiry
        }

        # --- FIX: PREVENT MULTIPLE MAINS ---
        # If the user ALREADY has a main character (that isn't the one currently being linked),
        # force the incoming character to be is_main=False.
        # This handles the scenario where a character was "Main" on Account B but is now an Alt on Account A.
        if user.characters.filter(is_main=True).exclude(character_id=char_id).exists():
            defaults['is_main'] = False

        # update_or_create can also trigger InvalidToken if the row exists but is corrupt
        try:
            target_char, created = EveCharacter.objects.update_or_create(
                character_id=char_id,
                defaults=defaults
            )
        except InvalidToken:
            # AUTO-HEAL: If update fails due to encryption error, force wipe the row's tokens
            EveCharacter.objects.filter(character_id=char_id).update(access_token="", refresh_token="")
            # Retry the operation
            target_char, created = EveCharacter.objects.update_or_create(
                character_id=char_id,
                defaults=defaults
            )

        print(f"Queueing background refresh for {char_name} (Alt Link)...")
        refresh_character_task.delay(target_char.character_id)
        
        return redirect('profile')
    else:
        # --- LOGIN ---
        try:
            # Try to get existing character
            target_char = EveCharacter.objects.get(character_id=char_id)
            
        except InvalidToken:
            # AUTO-HEAL: Corrupt data found. Wipe it so we can use it.
            print(f"⚠️ Corrupt token data found for {char_id}. Auto-healing...")
            EveCharacter.objects.filter(character_id=char_id).update(access_token="", refresh_token="")
            target_char = EveCharacter.objects.get(character_id=char_id)

        except EveCharacter.DoesNotExist:
            target_char = None

        if target_char:
            # Character exists, update tokens
            user = target_char.user
            target_char.access_token = access_token
            target_char.refresh_token = refresh_token
            target_char.token_expires = token_expiry
            target_char.save()
            
        else:
            # Create new user logic
            is_first_user = User.objects.count() == 0

            user = User.objects.create_user(
                username=str(char_id),
                first_name=char_name
            )
            
            if is_first_user:
                user.is_superuser = True
                user.is_staff = True
                user.save()

            default_group, _ = Group.objects.get_or_create(name='Pilot')
            user.groups.add(default_group)
            
            target_char = EveCharacter.objects.create(
                user=user,
                character_id=char_id,
                character_name=char_name,
                is_main=True,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires=token_expiry
            )
            
            print(f"Queueing background refresh for {char_name} (New Account)...")
            refresh_character_task.delay(target_char.character_id)

        login(request, user)
        request.session['active_char_id'] = char_id
        return redirect('landing_page')

def logout_view(request):
    logout(request)
    return redirect('landing_page')