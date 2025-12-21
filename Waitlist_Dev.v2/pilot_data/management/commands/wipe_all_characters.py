from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command
import time

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

        with connection.cursor() as cursor:
            if connection.vendor == 'mysql':
                self.stdout.write("Detected MySQL backend.")

                # 1. Kill other connections to free locks
                try:
                    self.stdout.write("Attempting to kill active connections...")
                    cursor.execute("SELECT DATABASE()")
                    db_name = cursor.fetchone()[0]

                    cursor.execute(
                        "SELECT id FROM information_schema.processlist WHERE db = %s AND id != CONNECTION_ID()",
                        [db_name]
                    )
                    processes = cursor.fetchall()

                    if processes:
                        self.stdout.write(f"Found {len(processes)} active connections. Terminating...")
                        for (pid,) in processes:
                            try:
                                cursor.execute(f"KILL {pid}")
                            except Exception as e:
                                self.stdout.write(self.style.WARNING(f"Could not kill process {pid}: {e}"))

                        # Give a moment for connections to close and locks to release
                        time.sleep(1)
                    else:
                        self.stdout.write("No other active connections found.")

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Error checking/killing connections: {e}"))

                # 2. Drop Tables
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                cursor.execute("SHOW TABLES;")
                tables = cursor.fetchall()

                for table in tables:
                    table_name = table[0]
                    self.stdout.write(f" -> Dropping table {table_name}...")
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`;")
                    except Exception as e:
                        # Retry once if lock wait timeout happens (in case KILL didn't clear it fast enough)
                        self.stdout.write(self.style.WARNING(f"Error dropping {table_name}: {e}. Retrying..."))
                        time.sleep(2)
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
