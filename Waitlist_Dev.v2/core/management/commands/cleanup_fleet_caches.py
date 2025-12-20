from django.core.management.base import BaseCommand
from pilot_data.models import EsiHeaderCache
from waitlist_data.models import Fleet
import re

class Command(BaseCommand):
    help = 'Cleans up ESI cache headers for fleets that are no longer active or have changed commanders.'

    def handle(self, *args, **options):
        self.stdout.write("Scanning for stale fleet caches...")

        # 1. Find all fleet-related cache entries
        # Keys are formatted like: fleet_members_{id} or fleet_wings_{id}
        fleet_caches = EsiHeaderCache.objects.filter(endpoint_name__startswith='fleet_')

        deleted_count = 0
        total_count = 0

        for cache_entry in fleet_caches:
            total_count += 1
            endpoint = cache_entry.endpoint_name

            # Extract Fleet ID
            # Regex to find digits at the end
            match = re.search(r'_(\d+)$', endpoint)
            if not match:
                continue

            esi_fleet_id = int(match.group(1))

            # Check Validity
            is_valid = False

            try:
                # Find active fleet with this ESI ID
                # We filter by is_active=True because closed fleets shouldn't be polled
                fleet = Fleet.objects.get(esi_fleet_id=esi_fleet_id, is_active=True)

                # Check if the cache owner is the current commander
                # The cache entry belongs to 'cache_entry.character'
                # The fleet commander is a User 'fleet.commander'
                # So we check if the cache char belongs to the commander user
                if cache_entry.character.user_id == fleet.commander_id:
                    is_valid = True
                else:
                    # Stale commander
                    pass

            except Fleet.DoesNotExist:
                # Fleet doesn't exist or is closed
                pass
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking fleet {esi_fleet_id}: {e}"))

            if not is_valid:
                cache_entry.delete()
                deleted_count += 1

        self.stdout.write(self.style.SUCCESS(f"Cleanup Complete. Scanned {total_count} entries. Deleted {deleted_count} stale entries."))
