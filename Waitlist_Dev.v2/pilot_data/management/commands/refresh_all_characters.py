import time
from django.core.management.base import BaseCommand
from pilot_data.models import EveCharacter
from scheduler.tasks import refresh_character_task

class Command(BaseCommand):
    help = 'Queues a background refresh for ALL characters in the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='How many tasks to queue before sleeping (Default: 50)'
        )
        parser.add_argument(
            '--sleep',
            type=int,
            default=10,
            help='Seconds to sleep between batches (Default: 10)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        sleep_time = options['sleep']

        # Count first (cheap query)
        total = EveCharacter.objects.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING("No characters found in database."))
            return

        self.stdout.write(self.style.HTTP_INFO(f"Found {total} characters."))
        self.stdout.write(f"Starting Slow-Roll Injection: {batch_size} tasks every {sleep_time}s...")
        self.stdout.write("------------------------------------------------------------")

        queued_count = 0
        
        # Use iterator() to stream results from DB instead of loading all into RAM
        # chunk_size on iterator() tells the DB driver how many rows to fetch per network roundtrip
        qs = EveCharacter.objects.values_list('character_id', flat=True).iterator(chunk_size=batch_size)
        
        batch = []
        for char_id in qs:
            batch.append(char_id)
            
            # When batch is full, process it
            if len(batch) >= batch_size:
                self._process_batch(batch)
                queued_count += len(batch)
                
                # Progress Update
                percent = int((queued_count / total) * 100)
                self.stdout.write(f"[{percent}%] Queued {len(batch)} tasks ({queued_count}/{total})...")
                
                # Sleep
                time.sleep(sleep_time)
                batch = [] # Reset batch

        # Process any remaining items
        if batch:
            self._process_batch(batch)
            queued_count += len(batch)
            self.stdout.write(f"[100%] Queued final {len(batch)} tasks.")

        self.stdout.write(self.style.SUCCESS(f"Done! Successfully queued {queued_count} character refreshes."))

    def _process_batch(self, batch):
        for char_id in batch:
            refresh_character_task.delay(char_id)