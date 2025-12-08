import json
import base64
from django.core.management.base import BaseCommand
from django.conf import settings
from pilot_data.models import EveCharacter

class Command(BaseCommand):
    help = 'Audits characters for missing ESI scopes, adjusting requirements based on User Role.'

    def handle(self, *args, **options):
        # 1. Define Scope Sets from Settings
        base_scopes = set(settings.EVE_SCOPES_BASE.split())
        fc_scopes = set(settings.EVE_SCOPES_FC.split())
        
        self.stdout.write("Scope Definitions:")
        self.stdout.write(f" - Base Scopes: {len(base_scopes)}")
        self.stdout.write(f" - FC Scopes:   {len(fc_scopes)}")
        self.stdout.write("-" * 40)

        issues_found = 0
        total_checked = 0

        for char in EveCharacter.objects.select_related('user').iterator():
            total_checked += 1
            
            if not char.access_token:
                self.stdout.write(self.style.ERROR(f"[NO TOKEN] {char.character_name}"))
                issues_found += 1
                continue

            # 2. Determine Required Scopes for THIS Character
            user = char.user
            # Check if user has FC capability (using the slug we migrated earlier)
            is_fc = user.groups.filter(capabilities__slug='access_fleet_command').exists() or user.is_superuser
            
            required_for_char = base_scopes.copy()
            if is_fc:
                required_for_char.update(fc_scopes)

            try:
                # 3. Decode Token
                parts = char.access_token.split('.')
                if len(parts) != 3:
                    self.stdout.write(self.style.WARNING(f"[BAD JWT] {char.character_name}"))
                    continue
                
                payload_part = parts[1]
                padding = '=' * (4 - len(payload_part) % 4)
                payload_str = base64.urlsafe_b64decode(payload_part + padding).decode('utf-8')
                payload = json.loads(payload_str)

                token_scopes_raw = payload.get('scp', [])
                if isinstance(token_scopes_raw, str):
                    current_scopes = {token_scopes_raw}
                else:
                    current_scopes = set(token_scopes_raw)

                # 4. Compare
                missing = required_for_char - current_scopes
                
                if missing:
                    role_label = "FC" if is_fc else "Pilot"
                    self.stdout.write(self.style.WARNING(f"[PARTIAL] {char.character_name} ({role_label})"))
                    self.stdout.write(f"    Missing: {', '.join(list(missing))}")
                    issues_found += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[ERROR] {char.character_name}: {e}"))

        self.stdout.write("-" * 40)
        if issues_found > 0:
            self.stdout.write(self.style.WARNING(f"Audit Complete. Found {issues_found} characters needing re-auth."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Audit Complete. All {total_checked} characters are authorized for their roles!"))