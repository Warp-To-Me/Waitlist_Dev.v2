import requests
import urllib.parse
import os
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User, Group
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from pilot_data.models import EveCharacter
from esi_calls.token_manager import update_character_data

def sso_login(request):
    if 'is_adding_alt' in request.session:
        del request.session['is_adding_alt']
    return _start_sso_flow(request)

@login_required
def add_alt(request):
    request.session['is_adding_alt'] = True
    return _start_sso_flow(request)

def _start_sso_flow(request):
    params = {
        'response_type': 'code',
        'redirect_uri': settings.EVE_CALLBACK_URL,
        'client_id': settings.EVE_CLIENT_ID,
        'scope': settings.EVE_SCOPES,
        'state': 'security_token_placeholder' 
    }
    base_url = "https://login.eveonline.com/v2/oauth/authorize/"
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)

def sso_callback(request):
    code = request.GET.get('code')
    if not code: return HttpResponse("SSO Error: No code received", status=400)

    # 1. Exchange code for tokens
    token_url = "https://login.eveonline.com/v2/oauth/token"
    client_id = settings.EVE_CLIENT_ID
    secret_key = os.getenv('EVE_SECRET_KEY')

    try:
        # Use Basic Auth for the code exchange (standard for Confidential Clients)
        auth_response = requests.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': code,
            },
            auth=(client_id, secret_key)
        )
        auth_response.raise_for_status()
    except Exception as e:
        return HttpResponse(f"Token Exchange Failed: {e} (Response: {auth_response.text if 'auth_response' in locals() else 'None'})", status=400)
    
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
        
        target_char, created = EveCharacter.objects.update_or_create(
            character_id=char_id,
            defaults={
                'user': user,
                'character_name': char_name,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_expires': token_expiry
            }
        )
        # Force immediate update so data is ready
        print(f"Linking complete. Fetching initial data for {char_name}...")
        update_character_data(target_char)
        
        return redirect('profile')
    else:
        # --- LOGIN ---
        try:
            target_char = EveCharacter.objects.get(character_id=char_id)
            user = target_char.user
            
            # Update tokens
            target_char.access_token = access_token
            target_char.refresh_token = refresh_token
            target_char.token_expires = token_expiry
            target_char.save()
            
            # Optional: Refresh data on login if it's very old
            # update_character_data(target_char) 

        except EveCharacter.DoesNotExist:
            # New User
            user = User.objects.create_user(username=char_name)
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
            # Force immediate update for new user
            print(f"New user created. Fetching initial data for {char_name}...")
            update_character_data(target_char)

        login(request, user)
        request.session['active_char_id'] = char_id
        return redirect('landing_page')

def logout_view(request):
    logout(request)
    return redirect('landing_page')