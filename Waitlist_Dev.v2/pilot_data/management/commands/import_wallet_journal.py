from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from pilot_data.models import CorpWalletJournal, EveCharacter, SRPConfiguration
import datetime
import os

class Command(BaseCommand):
    help = 'Imports legacy wallet history from SQL dump'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the SQL file')
        parser.add_argument(
            '--fix-divisions',
            action='store_true',
            help='Update division numbers for existing entries based on the SQL file.',
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        fix_divisions = options['fix_divisions']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        # Fetch a default SRPConfiguration to assign to these legacy entries.
        default_config = SRPConfiguration.objects.first()
        if not default_config:
            self.stdout.write(self.style.ERROR('Error: No SRPConfiguration found in the database.'))
            self.stdout.write(self.style.WARNING('Please create at least one SRP Configuration in the admin panel so these legacy entries can be assigned to it.'))
            return

        self.stdout.write(f'Using SRP Configuration: "{default_config}" (ID: {default_config.pk}) for import.')
        self.stdout.write(f'Reading file: {file_path}...')

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.stdout.write('Parsing SQL content...')

            rows = self.parse_sql_inserts(content)

            count = 0
            skipped = 0
            updated = 0
            batch_size = 1000
            batch = []

            # Helper to safely convert numbers that might be 'NULL'
            def safe_val(val, type_func, default):
                if val == 'NULL' or val is None:
                    return default
                try:
                    return type_func(val)
                except (ValueError, TypeError):
                    return default

            with transaction.atomic():
                for i, parts in enumerate(rows):
                    try:
                        # Filter out header rows or malformed lines
                        # Basic heuristic: 1st col should be a number (ID)
                        if not parts[0].replace("'", "").replace("`", "").isdigit():
                            continue

                        # Ensure we have enough columns (legacy format expected ~17 cols)
                        if len(parts) < 17:
                            continue

                        entry_id = int(parts[0])
                        division = safe_val(parts[2], int, 1)

                        # Check if exists (Performance: could batch this check too, but logic simpler this way for updates)
                        existing = CorpWalletJournal.objects.filter(entry_id=entry_id).first()

                        if existing:
                            if fix_divisions:
                                if existing.division != division:
                                    existing.division = division
                                    existing.save(update_fields=['division'])
                                    updated += 1
                            skipped += 1
                            continue

                        # Parse Date
                        date_str = parts[3]
                        try:
                            # Try standard SQL format
                            entry_date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                            entry_date = timezone.make_aware(entry_date)
                        except (ValueError, TypeError):
                            entry_date = timezone.now()

                        first_party_id = safe_val(parts[5], int, 0)
                        first_party_name = parts[6] if parts[6] != 'NULL' else ''

                        description = parts[16] if parts[16] != 'NULL' else ''
                        reason = parts[11] if parts[11] != 'NULL' else ''

                        entry = CorpWalletJournal(
                            entry_id=entry_id,
                            amount=safe_val(parts[9], float, 0.0),
                            balance=safe_val(parts[10], float, 0.0),
                            description=description,
                            reason=reason,
                            ref_type=parts[4],
                            date=entry_date,
                            first_party_id=first_party_id,
                            first_party_name=first_party_name,
                            second_party_id=safe_val(parts[7], int, 0),
                            second_party_name=parts[8] if parts[8] != 'NULL' else '',
                            tax=safe_val(parts[13], float, 0.0),
                            division=division,
                            config=default_config
                        )
                        batch.append(entry)

                        if len(batch) >= batch_size:
                            CorpWalletJournal.objects.bulk_create(batch, ignore_conflicts=True)
                            count += len(batch)
                            batch = []
                            self.stdout.write(f'Processed {count} entries...')

                    except Exception as e:
                        skipped += 1
                        continue

                # Flush remaining
                if batch:
                    CorpWalletJournal.objects.bulk_create(batch, ignore_conflicts=True)
                    count += len(batch)

            self.stdout.write(self.style.SUCCESS(f'Import Complete: {count} new, {skipped} skipped (duplicates/errors).'))
            if fix_divisions:
                self.stdout.write(self.style.SUCCESS(f'Updates: {updated} records corrected.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {e}'))
            import traceback
            traceback.print_exc()

    def parse_sql_inserts(self, content):
        """
        Parses SQL content looking for INSERT INTO ... VALUES (...) tuples.
        Handles escaped quotes and multiple INSERT statements.
        Yields a list of values for each valid row found.
        """
        length = len(content)
        idx = 0

        # State Machine constants
        STATE_SCAN = 0
        STATE_IN_TUPLE = 1
        STATE_IN_STRING = 2

        state = STATE_SCAN
        quote_char = None
        escaped = False

        current_row = []
        current_val = []

        while idx < length:
            char = content[idx]

            if state == STATE_SCAN:
                if char == '(':
                    state = STATE_IN_TUPLE
                    current_row = []
                    current_val = []

            elif state == STATE_IN_TUPLE:
                if char == "'" or char == '"':
                    state = STATE_IN_STRING
                    quote_char = char
                elif char == ',' and not escaped:
                    val = "".join(current_val).strip()
                    # Strip quoting from value if present (basic cleanup)
                    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                        val = val[1:-1]
                    current_row.append(val)
                    current_val = []
                elif char == ')' and not escaped:
                    val = "".join(current_val).strip()
                    if val:
                        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                            val = val[1:-1]
                        current_row.append(val)
                    yield current_row
                    state = STATE_SCAN
                else:
                    current_val.append(char)

            elif state == STATE_IN_STRING:
                if escaped:
                    current_val.append(char)
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == quote_char:
                    state = STATE_IN_TUPLE
                    quote_char = None
                else:
                    current_val.append(char)

            idx += 1
