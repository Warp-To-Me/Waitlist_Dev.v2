from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Removes all simulation users created by the simulate_load command.'

    def handle(self, *args, **options):
        # Identify sim users based on the naming convention used in simulate_load.py
        sim_users = User.objects.filter(username__startswith='sim_user_')
        count = sim_users.count()

        if count == 0:
            self.stdout.write(self.style.WARNING("No simulation users found."))
            return

        # Confirm before deleting if there are many (optional safety, but helpful)
        self.stdout.write(self.style.HTTP_INFO(f"Found {count} simulation users."))
        
        # Perform Deletion
        # This triggers CASCADE delete on EveCharacter -> WaitlistEntry -> FleetActivity
        sim_users.delete()

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {count} simulation users and cleaned up all associated data."))