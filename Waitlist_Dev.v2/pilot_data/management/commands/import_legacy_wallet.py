import re
import ast
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.db import transaction
from pilot_data.models import SRPConfiguration, CorpWalletJournal

class Command(BaseCommand):
    help = 'Imports historical wallet data from a HeidiSQL SQL export file.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the .sql file')

    def handle(self, *args, **options):
        file_path = options['file_path']
        
        # 1. Get Active SRP Config
        config = SRPConfiguration.objects.first()
        if not config:
            self.stdout.write(self.style.ERROR("No SRP Configuration found. Please set an SRP source in the web UI first."))
            return

        self.stdout.write(f"Importing to SRP Config: {config.character.character_name}")
        self.stdout.write("Reading file... (This may take a moment)")

        # 2. Regex to capture content between parentheses: (val1, val2), (val3, val4)
        # This regex handles basic quoted strings containing commas.
        value_pattern = re.compile(r"\((?:[^)(]+|'[^']*')+\)")

        entries_to_create = []
        total_read = 0
        total_created = 0

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # We only care about INSERT INTO lines
                if not line.strip().startswith("INSERT INTO"):
                    continue

                matches = value_pattern.findall(line)
                
                for match in matches:
                    try:
                        clean_match = match.replace("NULL", "None")
                        row = ast.literal_eval(clean_match)
                        
                        # --- COLUMN MAPPING (HEIDISQL EXPORT) ---
                        # 0: entry_id
                        # 1: owner_id (Skipped)
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
                        # 12: tax
                        # 13: context_id
                        # 14: context_id_type
                        # 15: UNKNOWN/NULL (Skipped)
                        # 16: description
                        # 17: custom_category (NEW)
                        # 18: timestamp (Skipped)

                        if len(row) < 17:
                            continue

                        entry = CorpWalletJournal(
                            config=config,
                            entry_id=row[0],
                            division=row[2],
                            date=parse_datetime(row[3]) if isinstance(row[3], str) else row[3],
                            ref_type=row[4],
                            first_party_id=row[5],
                            first_party_name=row[6] or "",
                            second_party_id=row[7],
                            second_party_name=row[8] or "",
                            amount=Decimal(str(row[9])),
                            balance=Decimal(str(row[10])),
                            reason=row[11] or "",
                            tax=Decimal(str(row[12])) if row[12] is not None else None,
                            context_id=row[13],
                            context_id_type=row[14],
                            description=row[16] or "",
                            custom_category=row[17] or "" # Capture Custom Category
                        )
                        entries_to_create.append(entry)
                        total_read += 1

                    except (ValueError, SyntaxError, InvalidOperation) as e:
                        continue

                    if len(entries_to_create) >= 5000:
                        self._bulk_insert(entries_to_create)
                        total_created += len(entries_to_create)
                        entries_to_create = []
                        self.stdout.write(f"Processed {total_read} rows...")

        if entries_to_create:
            self._bulk_insert(entries_to_create)
            total_created += len(entries_to_create)

        self.stdout.write(self.style.SUCCESS(f"Import Complete. Processed {total_read} lines."))

    def _bulk_insert(self, entries):
        # ignore_conflicts=True ensures we skip any rows that already exist in DB
        CorpWalletJournal.objects.bulk_create(entries, ignore_conflicts=True)