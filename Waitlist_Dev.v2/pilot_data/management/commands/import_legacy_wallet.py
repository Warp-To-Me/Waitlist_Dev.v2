from django.core.management.base import BaseCommand
from django.utils import timezone
from pilot_data.models import CorpWalletJournal, EveCharacter, SRPConfiguration
import datetime
import os

class Command(BaseCommand):
    help = 'Imports legacy wallet history from SQL dump'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the SQL file')

    def handle(self, *args, **options):
        file_path = options['file_path']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        # Fetch a default SRPConfiguration to assign to these legacy entries.
        # This is required because 'config_id' is non-nullable in the database.
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
            errors_printed = 0
            
            # Cache characters to avoid DB hammering
            char_cache = {}

            for i, parts in enumerate(rows):
                try:
                    # Filter out header rows (like `transaction_id`, `corporation_id`, etc.)
                    # If the first column isn't a number (after stripping quotes/backticks), it's a column definition.
                    if not parts[0].replace("'", "").replace("`", "").isdigit():
                        continue

                    # Mapping based on your provided SQL snippet:
                    # 0: transaction_id
                    # 1: corporation_id
                    # 2: division
                    # 3: date
                    # 4: ref_type
                    # 5: first_party_id
                    # 6: first_party_name
                    # 7: second_party_id
                    # 8: second_party_name
                    # 9: amount
                    # 10: balance
                    # 11: reason
                    # 12: tax_receiver_id (Ignored)
                    # 13: tax_amount
                    # 16: description
                    
                    if len(parts) < 17:
                        continue

                    entry_id = int(parts[0])
                    
                    # Check if exists
                    if CorpWalletJournal.objects.filter(entry_id=entry_id).exists():
                        skipped += 1
                        continue

                    # Helper to safely convert numbers that might be 'NULL'
                    def safe_val(val, type_func, default):
                        if val == 'NULL' or val is None:
                            return default
                        try:
                            return type_func(val)
                        except (ValueError, TypeError):
                            return default

                    # Parse Date
                    date_str = parts[3]
                    try:
                        entry_date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        entry_date = timezone.make_aware(entry_date)
                    except (ValueError, TypeError):
                        entry_date = timezone.now()

                    first_party_id = safe_val(parts[5], int, 0)
                    first_party_name = parts[6] if parts[6] != 'NULL' else ''
                    
                    # Clean strings
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
                        # Map tax from column 13
                        tax=safe_val(parts[13], float, 0.0),
                        # Assign the default configuration found earlier
                        config=default_config
                    )
                    entry.save()
                    count += 1
                    
                    if count % 1000 == 0:
                        self.stdout.write(f'Processed {count} entries...')

                except Exception as e:
                    skipped += 1
                    # Print the first few errors to help debug data issues
                    if errors_printed < 5:
                        self.stdout.write(self.style.WARNING(f"Error on row {i+1}: {e}"))
                        self.stdout.write(f"Row data: {parts}")
                        errors_printed += 1
                    continue

            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} wallet journal entries. Skipped {skipped} existing/invalid.'))

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
                    current_row.append(val)
                    current_val = []
                elif char == ')' and not escaped:
                    val = "".join(current_val).strip()
                    if val:
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