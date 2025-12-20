from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from pilot_data.models import EveCharacter
from esi_calls.token_manager import update_character_data, ENDPOINT_SHIP

class Command(BaseCommand):
    help = 'Verifies the ESI Ship endpoint migration by syncing a user\'s ship.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username of the user to test.')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found."))
            return

        # Find main character or first character
        try:
            char = user.characters.filter(is_main=True).first()
            if not char:
                char = user.characters.first()
            
            if not char:
                self.stdout.write(self.style.ERROR(f"User '{username}' has no linked characters."))
                return

            self.stdout.write(self.style.SUCCESS(f"Testing Ship Sync for Character: {char.character_name}"))
            self.stdout.write(f"Pre-Sync: {char.current_ship_name} (ID: {char.current_ship_type_id})")

            # Execute Sync
            success = update_character_data(char, target_endpoints=[ENDPOINT_SHIP])

            char.refresh_from_db()

            if success:
                self.stdout.write(self.style.SUCCESS("Sync Function Returned: True"))
                self.stdout.write(self.style.SUCCESS(f"Post-Sync: {char.current_ship_name} (ID: {char.current_ship_type_id})"))
                self.stdout.write(self.style.SUCCESS("If you see the ship name updated or confirmed, the migration is working!"))
            else:
                self.stdout.write(self.style.ERROR("Sync Function Returned: False (Check logs for 'ESI Library Error' or Rate Limit warnings)"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Exception during test: {e}"))
