from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from pilot_data.models import EveCharacter, CharacterSkill, CharacterQueue
from esi_calls.token_manager import update_character_data, ENDPOINT_SKILLS, ENDPOINT_QUEUE, ENDPOINT_PUBLIC_INFO

class Command(BaseCommand):
    help = 'Verifies the ESI Core endpoints (Skills, Queue, Public Info) migration.'

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

        self.stdout.write(self.style.SUCCESS(f"Testing Core Sync for Character: {char.character_name}"))
        self.stdout.write(f"Pre-Sync: Corp={char.corporation_name}, SP={char.total_sp}")

        # Execute Sync
        success = update_character_data(char, target_endpoints=[ENDPOINT_SKILLS, ENDPOINT_QUEUE, ENDPOINT_PUBLIC_INFO])

        char.refresh_from_db()

        if success:
            self.stdout.write(self.style.SUCCESS("Sync Function Returned: True"))
            self.stdout.write(self.style.SUCCESS(f"Post-Sync: Corp={char.corporation_name}, SP={char.total_sp}"))

            queue_count = CharacterQueue.objects.filter(character=char).count()
            skill_count = CharacterSkill.objects.filter(character=char).count()

            self.stdout.write(f"Skills Stored: {skill_count}")
            self.stdout.write(f"Queue Items Stored: {queue_count}")

            if skill_count > 0:
                 self.stdout.write(self.style.SUCCESS("Skills migration appears successful."))
            else:
                 self.stdout.write(self.style.WARNING("No skills found. Check if character has skills or if migration failed."))

        else:
            self.stdout.write(self.style.ERROR("Sync Function Returned: False (Check logs)"))
