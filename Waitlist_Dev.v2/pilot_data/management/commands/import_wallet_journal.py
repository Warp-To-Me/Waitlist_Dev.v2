from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from pilot_data.models import CorpWalletJournal, EveCharacter, SRPConfiguration
from esi_calls.wallet_service import determine_auto_category
import datetime
import os

class Command(BaseCommand):
    help = 'Imports legacy wallet history from SQL dump (Format: id, entry_id, amount, balance, ...)'

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
                        # Schema Mapping based on provided SQL:
                        # 0: id (local)
                        # 1: entry_id
                        # 2: amount
                        # 3: balance
                        # 4: context_id
                        # 5: context_id_type
                        # 6: date
                        # 7: description
                        # 8: first_party_id
                        # 9: second_party_id
                        # 10: reason
                        # 11: ref_type
                        # 12: tax
                        # 13: division
                        # 14: first_party_name
                        # 15: second_party_name
                        # 16: config_id
                        # 17: custom_category

                        if len(parts) < 18:
                            # Try to be lenient if optional cols at end are missing, but warn if strict
                            if len(parts) < 14:
                                continue

                        entry_id = int(parts[1]) # Index 1 is ESI Entry ID
                        division = safe_val(parts[13], int, 1) # Index 13

                        # Check if exists
                        existing = CorpWalletJournal.objects.filter(entry_id=entry_id).first()

                        if existing:
                            if fix_divisions:
                                if existing.division != division:
                                    existing.division = division
                                    existing.save(update_fields=['division'])
                                    updated += 1
                            skipped += 1
                            continue

                        # Parse Date (Index 6)
                        date_str = parts[6]
                        try:
                            # Try standard SQL format: '2025-12-17 03:18:59.000000'
                            # remove microseconds if causing issues or use flexible parser
                            if '.' in date_str:
                                dt_part, _ = date_str.split('.')
                            else:
                                dt_part = date_str

                            entry_date = datetime.datetime.strptime(dt_part, '%Y-%m-%d %H:%M:%S')
                            entry_date = timezone.make_aware(entry_date)
                        except (ValueError, TypeError):
                            entry_date = timezone.now()

                        first_party_id = safe_val(parts[8], int, 0)
                        second_party_id = safe_val(parts[9], int, 0)

                        amount = safe_val(parts[2], float, 0.0)
                        reason = parts[10] if parts[10] != 'NULL' else ''
                        ref_type = parts[11] if parts[11] != 'NULL' else ''

                        # Handle Custom Category
                        # If the SQL has it (Index 17), use it. If 'NULL', try to calculate it.
                        custom_cat = None
                        if len(parts) > 17 and parts[17] != 'NULL':
                            custom_cat = parts[17]

                        if not custom_cat:
                             custom_cat = determine_auto_category(
                                 amount, reason, first_party_id, second_party_id,
                                 default_config.character.corporation_id, ref_type
                             )

                        entry = CorpWalletJournal(
                            entry_id=entry_id,
                            amount=amount,
                            balance=safe_val(parts[3], float, 0.0),
                            context_id=safe_val(parts[4], int, 0),
                            context_id_type=parts[5] if parts[5] != 'NULL' else '',
                            date=entry_date,
                            description=parts[7] if parts[7] != 'NULL' else '',
                            first_party_id=first_party_id,
                            second_party_id=second_party_id,
                            reason=reason,
                            ref_type=ref_type,
                            tax=safe_val(parts[12], float, 0.0),
                            division=division,
                            first_party_name=parts[14] if parts[14] != 'NULL' else '',
                            second_party_name=parts[15] if parts[15] != 'NULL' else '',
                            custom_category=custom_cat,
                            config=default_config
                        )
                        batch.append(entry)

                        if len(batch) >= batch_size:
                            CorpWalletJournal.objects.bulk_create(batch, ignore_conflicts=True)
                            count += len(batch)
                            batch = []
                            self.stdout.write(f'Processed {count} entries...')

                    except Exception as e:
                        # self.stdout.write(f"Row Error: {e}")
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
