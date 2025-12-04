import json
import base64
from django.core.management.base import BaseCommand
from django.conf import settings
from pilot_data.models import EveCharacter

class Command(BaseCommand):
    help = 'Audits all characters to find those missing required ESI scopes.'

    def handle(self, *args, **options):
        # 1. Get the "Gold Standard" list of scopes from settings
        # The setting is a space-separated string, so we split it into a set
        required_scopes = set(settings.EVE_SCOPES.split())
        
        self.stdout.write(f"Auditing against {len(required_scopes)} required scopes:")
        for s in required_scopes:
            self.stdout.write(f" - {s}")
        self.stdout.write("-" * 40)

        issues_found = 0
        total_checked = 0

        # 2. Iterate all characters
        # We use iterator() for memory efficiency if you have thousands of users
        for char in EveCharacter.objects.all().iterator():
            total_checked += 1
            
            if not char.access_token:
                self.stdout.write(self.style.ERROR(f"[MISSING TOKEN] {char.character_name} (ID: {char.character_id})"))
                issues_found += 1
                continue

            try:
                # 3. Decode the JWT (Access Token)
                # JWTs are "header.payload.signature". We need the middle part.
                # We don't need to verify the signature here (ESI does that), just read the claims.
                parts = char.access_token.split('.')
                if len(parts) != 3:
                    self.stdout.write(self.style.WARNING(f"[INVALID JWT] {char.character_name}"))
                    continue
                
                # Padding fix for Base64 decoding
                payload_part = parts[1]
                padding = '=' * (4 - len(payload_part) % 4)
                payload_str = base64.urlsafe_b64decode(payload_part + padding).decode('utf-8')
                payload = json.loads(payload_str)

                # 4. Extract Scopes from Token
                # 'scp' can be a list or a single string
                token_scopes_raw = payload.get('scp', [])
                if isinstance(token_scopes_raw, str):
                    token_scopes = {token_scopes_raw}
                else:
                    token_scopes = set(token_scopes_raw)

                # 5. Compare
                missing = required_scopes - token_scopes
                
                if missing:
                    self.stdout.write(self.style.WARNING(f"[MISSING SCOPES] {char.character_name}"))
                    for m in missing:
                        self.stdout.write(f"    - {m}")
                    issues_found += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[ERROR] {char.character_name}: {e}"))

        self.stdout.write("-" * 40)
        if issues_found > 0:
            self.stdout.write(self.style.WARNING(f"Audit Complete. Found {issues_found} characters with issues out of {total_checked}."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Audit Complete. All {total_checked} characters are fully authorized!"))