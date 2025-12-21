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

# ESI Library Imports
from esi.clients import EsiClientProvider
from esi.models import Token, Scope

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
    
    mode = request.GET.get('mode') if request.method == 'GET' else request.data.get('mode')

    is_fc = False
    if request.user.is_authenticated:
        is_fc = request.user.is_superuser or \
                request.user.groups.filter(capabilities__slug='access_fleet_command').exists()

    # Determine which optional scopes are allowed/visible
    allowed_optional_list = list(optional_scopes)
    if is_fc and mode == 'fc_auth':
        allowed_optional_list += fc_scopes

    if request.method == 'GET':
        scope_options = []
        for scope in allowed_optional_list:
            meta = settings.SCOPE_DESCRIPTIONS.get(scope, {'label': scope, 'description': ''})
            scope_options.append({
                'scope': scope,
                'label': meta['label'],
                'description': meta['description']
            })
            
        base_options = []
        # Copy base_scopes to avoid mutating the original setting list in memory if it was mutable (though split() creates new)
        current_base_scopes = list(base_scopes)

        # If SRP Config/Auth mode, treat SRP scopes as Base (Required) scopes
        if mode == 'srp_config' or mode == 'srp_auth':
             current_base_scopes.extend(srp_scopes)

        for scope in current_base_scopes:
             meta = settings.SCOPE_DESCRIPTIONS.get(scope, {'label': scope, 'description': ''})
             base_options.append({
                'scope': scope,
                'label': meta['label'],
                'description': meta['description']
            })

        # Calculate pre-selected scopes
        preselected = []
        if request.user.is_authenticated:
            if mode == 'fc_auth' and is_fc:
                preselected.extend(fc_scopes)
            elif mode == 'add_alt':
                # Attempt to find main character to copy scopes from
                main_char = request.user.characters.filter(is_main=True).first()
                if not main_char and request.user.characters.exists():
                    main_char = request.user.characters.first()
                
                if main_char and main_char.granted_scopes:
                    granted = set(main_char.granted_scopes.split())
                    # Only pre-select scopes that are actually available/optional
                    # (Prevent copying legacy scopes or invalid ones)
                    valid_optional = set(allowed_optional_list)
                    for scope in granted:
                        if scope in valid_optional:
                            preselected.append(scope)

        return JsonResponse({
            'base_scopes': base_options,
            'optional_scopes': scope_options,
            'preselected_scopes': preselected
        })

    if request.method == 'POST':
        data = request.data
        requested_custom = data.get('scopes', [])
        
        # Set session flags based on mode
        _clear_session_flags(request)
        if mode == 'add_alt' or mode == 'fc_auth':
            if not request.user.is_authenticated:
                return HttpResponse("Authentication required to add alt", status=403)
            request.session['is_adding_alt'] = True
        
        elif mode == 'srp_auth' or mode == 'srp_config':
            if not request.user.is_authenticated or not can_manage_srp(request.user):
                 return HttpResponse("Permission denied for SRP auth", status=403)
            request.session['is_adding_alt'] = True
            request.session['is_srp_auth'] = True

        # Always include Base Scopes
        final_scopes = set(base_scopes)
        
        # Add valid custom scopes
        allowed_optional_set = set(allowed_optional_list)
        for s in requested_custom:
            if s in allowed_optional_set:
                final_scopes.add(s)

        # If SRP Auth mode, enforce SRP scopes
        if mode == 'srp_auth' or mode == 'srp_config':
             for s in srp_scopes:
                 final_scopes.add(s)
        
        # --- ESI LIBRARY INTEGRATION ---
        # We now use the ESI provider to generate the URL, ensuring consistent state/scopes
        cprovider = EsiClientProvider(app_settings=None) 
        # Note: EsiClientProvider uses settings.ESI_SSO_... by default if app_settings is None
        
        scope_str = " ".join(final_scopes)
        
        # We still use our manual state handling for session tracking
        state_token = secrets.token_urlsafe(32)
        request.session['sso_state'] = state_token
        
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
@user_passes_test(can_manage_srp)
def srp_auth(request):
    _clear_session_flags(request)
    request.session['is_adding_alt'] = True
    request.session['is_srp_auth'] = True
    return _start_sso_flow(request)

@login_required
@user_passes_test(can_manage_srp)
def srp_config(request):
    return srp_auth(request)

def _clear_session_flags(request):
    keys = ['is_adding_alt', 'is_srp_auth', 'sso_state']
    for k in keys:
        if k in request.session:
            del request.session[k]

def _start_sso_flow(request):
    state_token = secrets.token_urlsafe(32)
    request.session['sso_state'] = state_token

    if request.session.get('is_srp_auth'):
        scopes = getattr(settings, 'EVE_SCOPES', settings.EVE_SCOPES_BASE)
    else:
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

    saved_state = request.session.get('sso_state')
    is_adding = request.session.get('is_adding_alt')
    is_srp = request.session.get('is_srp_auth')
    
    _clear_session_flags(request)
    
    if not state or state != saved_state:
        # State mismatch
        pass 

    if not code: return HttpResponse("SSO Error: No code received", status=400)

    # 1. Exchange code for tokens (Using ESI Library!)
    # Token.objects.create_from_code handles code exchange, verification, and saving.
    try:
        esi_token = Token.objects.create_from_code(code)
    except Exception as e:
        return HttpResponse(f"Token Exchange Failed: {e}", status=400)
    
    # 2. Sync with our Local Models
    # We still need EveCharacter for our app's logic (skills, history, etc),
    # but we no longer need to store the raw tokens there.
    
    user = request.user
    
    if user.is_authenticated and is_adding:
        # --- ADDING / UPDATING ALT ---
        # Update ownership of the ESI Token to the current user
        esi_token.user = user
        esi_token.save()
        
        # Link/Update EveCharacter
        defaults = {
            'user': user,
            'character_name': esi_token.character_name,
            # We keep granted_scopes string for easy query filtering in legacy code
            'granted_scopes': " ".join([s.name for s in esi_token.scopes.all()])
        }

        if user.characters.filter(is_main=True).exclude(character_id=esi_token.character_id).exists():
            defaults['is_main'] = False

        target_char, created = EveCharacter.objects.update_or_create(
            character_id=esi_token.character_id,
            defaults=defaults
        )
        
        refresh_character_task.delay(target_char.character_id)
        
        if is_srp:
            return redirect('/management/srp/config')
        return redirect('/profile')
        
    else:
        # --- LOGIN ---
        # Ensure Token has a user. If not, we create/find one.
        
        target_char = EveCharacter.objects.filter(character_id=esi_token.character_id).first()
        
        if target_char:
            # Existing Character -> Log in as this user
            user = target_char.user
            # Ensure ESI Token is owned by this user
            if esi_token.user != user:
                esi_token.user = user
                esi_token.save()
                
            # Update scopes cache
            target_char.granted_scopes = " ".join([s.name for s in esi_token.scopes.all()])
            target_char.save()
            
        else:
            # New User / New Character
            
            # Check if this ESI Token already has a user (maybe from a previous login that created it?)
            if esi_token.user:
                user = esi_token.user
            else:
                is_first_user = User.objects.count() == 0
                user = User.objects.create_user(username=str(esi_token.character_id), first_name=esi_token.character_name)
                
                if is_first_user:
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()

                default_group, _ = Group.objects.get_or_create(name='Public')
                user.groups.add(default_group)
                
                # Assign to token
                esi_token.user = user
                esi_token.save()

            # Create EveCharacter
            target_char = EveCharacter.objects.create(
                user=user,
                character_id=esi_token.character_id,
                character_name=esi_token.character_name,
                is_main=True,
                granted_scopes=" ".join([s.name for s in esi_token.scopes.all()])
            )
            refresh_character_task.delay(target_char.character_id)

        login(request, user)
        request.session['active_char_id'] = esi_token.character_id
        return redirect('/')

def logout_view(request):
    logout(request)
    return redirect('/')
