from django.core.management.base import BaseCommand
from pilot_data.models import EveCharacter
from esi.models import Token, Scope
from django.utils import timezone
from datetime import timedelta
import logging
import requests
import os
from django.conf import settings

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrates EveCharacter tokens to ESI Tokens'

    def handle(self, *args, **options):
        logger.info("Starting Token Migration...")
        count = 0

        # Encrypted fields don't support db-level filtering for 'exact' or 'exclude' on the content
        # We must fetch all and filter in python, or use isnull check only if supported.
        # EncryptedTextField supports isnull check usually.
        characters = EveCharacter.objects.exclude(refresh_token__isnull=True)

        for char in characters:
            if not char.refresh_token:
                continue
            try:
                # ESI Token Model requires:
                # - access_token, refresh_token
                # - user (ForeignKey)
                # - character_id, character_name, character_owner_hash

                owner_hash = "migration_placeholder"
                access_token = char.access_token
                refresh_token = char.refresh_token

                # 1. Try to verify with current access token
                headers = {'Authorization': f'Bearer {access_token}'}
                verify_url = "https://esi.evetech.net/verify/"

                try:
                    resp = requests.get(verify_url, headers=headers, timeout=5)
                except requests.RequestException:
                    resp = None

                if resp and resp.status_code == 200:
                    data = resp.json()
                    owner_hash = data['CharacterOwnerHash']
                else:
                    # 2. Token is likely expired. Refresh it manually to get hash.
                    token_url = "https://login.eveonline.com/v2/oauth/token"
                    client_id = settings.EVE_CLIENT_ID
                    secret_key = os.getenv('EVE_SECRET_KEY')

                    if not secret_key:
                        logger.error(f"Cannot refresh token for {char.character_name}: Missing EVE_SECRET_KEY")
                        continue

                    try:
                        refresh_resp = requests.post(
                            token_url,
                            data={'grant_type': 'refresh_token', 'refresh_token': refresh_token},
                            auth=(client_id, secret_key),
                            timeout=10
                        )

                        if refresh_resp.status_code == 200:
                            tokens = refresh_resp.json()
                            access_token = tokens['access_token']
                            refresh_token = tokens.get('refresh_token', refresh_token)

                            # Retry Verify with new token
                            headers = {'Authorization': f'Bearer {access_token}'}
                            verify_resp = requests.get(verify_url, headers=headers, timeout=5)

                            if verify_resp.status_code == 200:
                                owner_hash = verify_resp.json()['CharacterOwnerHash']
                            else:
                                logger.warning(f"Refreshed token but verify failed for {char.character_name}")
                        else:
                            logger.warning(f"Failed to refresh token for {char.character_name}: {refresh_resp.status_code}")

                    except Exception as e:
                        logger.error(f"Exception during refresh for {char.character_name}: {e}")

                if owner_hash == "migration_placeholder":
                    logger.warning(f"Skipping {char.character_name} - could not verify owner hash. User will need to re-login.")
                    continue

                # Create the Token
                token, created = Token.objects.update_or_create(
                    character_id=char.character_id,
                    defaults={
                        'character_name': char.character_name,
                        'user': char.user,
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'token_type': Token.TOKEN_TYPE_CHARACTER,
                        'character_owner_hash': owner_hash,
                    }
                )

                # scopes
                if char.granted_scopes:
                    scope_list = char.granted_scopes.split()
                    for s_name in scope_list:
                        scope_obj, _ = Scope.objects.get_or_create(name=s_name)
                        token.scopes.add(scope_obj)

                count += 1

            except Exception as e:
                logger.error(f"Failed to migrate {char.character_name}: {e}")

        self.stdout.write(self.style.SUCCESS(f'Successfully migrated {count} tokens'))
