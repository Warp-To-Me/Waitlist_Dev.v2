from django.core.management.base import BaseCommand
from django.db.models import Q
from pilot_data.models import CorpWalletJournal
# Imports the shared, case-insensitive logic we just created
from esi_calls.wallet_service import determine_auto_category

class Command(BaseCommand):
    help = 'Applies auto-categorization rules to existing wallet entries.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite ALL entries, even those that already have a category set.',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        self.stdout.write("Fetching wallet entries...")
        
        # 1. Select targets
        if force:
            qs = CorpWalletJournal.objects.all()
            self.stdout.write(self.style.WARNING("Running in FORCE mode. Re-evaluating ALL entries."))
        else:
            # Default: Only update entries that have NO category
            qs = CorpWalletJournal.objects.filter(Q(custom_category__isnull=True) | Q(custom_category=""))
            self.stdout.write("Running in SAFE mode. Only updating unclassified entries.")

        # Optimization: Fetch related config to get Corp ID efficiently
        qs = qs.select_related('config__character')
        
        total_count = qs.count()
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No entries to process."))
            return

        self.stdout.write(f"Processing {total_count} entries...")
        
        updated_objs = []
        updates_count = 0
        BATCH_SIZE = 1000
        
        # 2. Iterate and Update
        for entry in qs.iterator(chunk_size=2000):
            # We need the corp_id to detect internal transfers
            corp_id = entry.config.character.corporation_id
            
            # Use the shared logic (which is now case-insensitive)
            new_cat = determine_auto_category(
                entry.amount, 
                entry.reason, 
                entry.first_party_id, 
                entry.second_party_id, 
                corp_id
            )
            
            if new_cat:
                # Only save if it actually changes
                if entry.custom_category != new_cat:
                    entry.custom_category = new_cat
                    updated_objs.append(entry)
                    updates_count += 1
            
            # Bulk Update in batches
            if len(updated_objs) >= BATCH_SIZE:
                CorpWalletJournal.objects.bulk_update(updated_objs, ['custom_category'])
                self.stdout.write(f"Updated {updates_count} records...")
                updated_objs = []

        # Final Flush
        if updated_objs:
            CorpWalletJournal.objects.bulk_update(updated_objs, ['custom_category'])
            
        self.stdout.write(self.style.SUCCESS(f"Complete. Categorized {updates_count} / {total_count} entries."))