from django.core.management.base import BaseCommand
from pilot_data.models import EsiHeaderCache

class Command(BaseCommand):
    help = 'Removes deprecated online endpoint cache entries.'

    def handle(self, *args, **options):
        self.stdout.write("Scanning for deprecated 'online' cache entries...")
        
        count = EsiHeaderCache.objects.filter(endpoint_name='online').count()
        self.stdout.write(f"Found {count} entries.")
        
        if count > 0:
            deleted, _ = EsiHeaderCache.objects.filter(endpoint_name='online').delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} entries."))
        else:
            self.stdout.write(self.style.SUCCESS("No entries to delete."))
