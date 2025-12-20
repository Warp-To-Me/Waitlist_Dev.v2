from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from pilot_data.models import EveCharacter, CharacterImplant, CharacterHistory
from esi_calls.token_manager import update_character_data, ENDPOINT_WALLET, ENDPOINT_LP, ENDPOINT_IMPLANTS, ENDPOINT_HISTORY

class Command(BaseCommand):
    help = 'Verifies the ESI Remainder endpoints (Wallet, LP, Implants, History) migration.'

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
        char = user.characters.filter(is_main=True).first()
        if not char:
            char = user.characters.first()
        
        if not char:
            self.stdout.write(self.style.ERROR(f"User '{username}' has no linked characters."))
            return

        self.stdout.write(self.style.SUCCESS(f"Testing Remainder Sync for Character: {char.character_name}"))
        self.stdout.write(f"Pre-Sync: Wallet={char.wallet_balance}, LP={char.concord_lp}")

        # Execute Sync
        success = update_character_data(char, target_endpoints=[ENDPOINT_WALLET, ENDPOINT_LP, ENDPOINT_IMPLANTS, ENDPOINT_HISTORY])

        char.refresh_from_db()

        if success:
            self.stdout.write(self.style.SUCCESS("Sync Function Returned: True"))
            self.stdout.write(self.style.SUCCESS(f"Post-Sync: Wallet={char.wallet_balance}, LP={char.concord_lp}"))
            
            imp_count = CharacterImplant.objects.filter(character=char).count()
            hist_count = CharacterHistory.objects.filter(character=char).count()
            
            self.stdout.write(f"Implants: {imp_count}")
            self.stdout.write(f"History Entries: {hist_count}")
            
            if hist_count > 0:
                 self.stdout.write(self.style.SUCCESS("History migration appears successful."))
            else:
                 self.stdout.write(self.style.WARNING("No history found. Check if character has corp history."))

        else:
            self.stdout.write(self.style.ERROR("Sync Function Returned: False (Check logs)"))
