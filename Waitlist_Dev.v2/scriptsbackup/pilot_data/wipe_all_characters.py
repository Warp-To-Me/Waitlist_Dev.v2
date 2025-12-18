from django.core.management.base import BaseCommand
from django.db import connection, transaction

class Command(BaseCommand):
    help = 'FACTORY RESET: Wipes Characters, Users, Fleets, and all related data via Raw SQL.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip the confirmation prompt',
        )

    def handle(self, *args, **options):
        # Safety Confirmation
        if not options['force']:
            self.stdout.write(self.style.WARNING(
                "⚠️  WARNING: This is a FACTORY RESET.\n"
                "It will delete:\n"
                " - All EVE Characters (Skills, Implants, History)\n"
                " - All Django Users (Login accounts)\n"
                " - All Fleets\n"
                " - All Sessions and Admin Logs\n"
            ))
            confirm = input("Are you sure you want to proceed? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        self.stdout.write("Initializing Factory Reset...")

        # We use a transaction block to ensure everything commits
        with transaction.atomic():
            with connection.cursor() as cursor:
                # 1. Disable Foreign Key Checks (Crucial for Raw SQL deletion order)
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

                tables_to_wipe = [
                    # Child Data
                    'pilot_data_characterskill',
                    'pilot_data_characterqueue',
                    'pilot_data_characterimplant',
                    'pilot_data_characterhistory',
                    'pilot_data_esiheadercache',
                    
                    # App Data
                    'waitlist_data_fleet',
                    'django_admin_log',
                    
                    # Core Data
                    'pilot_data_evecharacter',
                    
                    # Auth Data (User & Groups)
                    'auth_user_groups',
                    'auth_user_user_permissions',
                    'auth_user',
                    
                    # Session Data (Logs everyone out)
                    'django_session',
                ]

                for table in tables_to_wipe:
                    self.stdout.write(f" -> Wiping {table}...")
                    cursor.execute(f"DELETE FROM {table};")

                # 2. Re-enable Foreign Key Checks
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        self.stdout.write(self.style.SUCCESS("SUCCESS: Factory Reset Complete. Database is clean."))