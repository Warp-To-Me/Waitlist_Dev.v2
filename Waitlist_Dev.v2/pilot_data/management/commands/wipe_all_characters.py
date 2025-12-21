from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.core.management import call_command

class Command(BaseCommand):
    help = 'FACTORY RESET: Wipes ALL database tables and re-runs migrations.'

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
                "It will delete ALL DATA in the database (Tables will be dropped).\n"
                "This action is irreversible.\n"
            ))
            confirm = input("Are you sure you want to proceed? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        self.stdout.write("Initializing Factory Reset...")

        # We use a transaction block where possible, but DDL statements (DROP TABLE)
        # often cause implicit commits in MySQL, so atomic might not cover everything.
        # However, we are destroying everything anyway.

        with connection.cursor() as cursor:
            if connection.vendor == 'mysql':
                self.stdout.write("Detected MySQL backend.")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                cursor.execute("SHOW TABLES;")
                tables = cursor.fetchall()

                for table in tables:
                    table_name = table[0]
                    self.stdout.write(f" -> Dropping table {table_name}...")
                    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`;")

                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

            elif connection.vendor == 'sqlite':
                self.stdout.write("Detected SQLite backend.")
                cursor.execute("PRAGMA foreign_keys = OFF;")
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()

                for table in tables:
                    table_name = table[0]
                    if table_name.startswith('sqlite_'):
                        continue
                    self.stdout.write(f" -> Dropping table {table_name}...")
                    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}";')

                cursor.execute("PRAGMA foreign_keys = ON;")

            else:
                self.stdout.write(self.style.ERROR(f"Unsupported database vendor: {connection.vendor}"))
                return

        self.stdout.write(self.style.SUCCESS("All tables dropped. Running migrations..."))

        # Run Migrations
        call_command('migrate')

        self.stdout.write(self.style.SUCCESS("SUCCESS: Factory Reset Complete. Database is clean and schema is fresh."))
