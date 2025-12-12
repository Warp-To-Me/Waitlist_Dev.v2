from django.core.management.base import BaseCommand
from pilot_data.models import EveCharacter
from waitlist_data.models import FleetActivity, CharacterStats
from collections import defaultdict
from django.utils import timezone

class Command(BaseCommand):
    help = 'Re-calculates ALL pilot stats from FleetActivity logs and populates CharacterStats table.'

    def handle(self, *args, **options):
        self.stdout.write("Fetching all characters...")
        
        chars = EveCharacter.objects.all()
        total = chars.count()
        processed = 0
        
        self.stdout.write(f"Found {total} characters. Starting backfill...")

        for char in chars:
            self._process_character(char)
            processed += 1
            if processed % 10 == 0:
                self.stdout.write(f"Processed {processed}/{total}...")

        self.stdout.write(self.style.SUCCESS("Backfill Complete."))

    def _process_character(self, character):
        # Fetch all historical logs for this character
        logs = FleetActivity.objects.filter(character=character).order_by('timestamp')
        
        total_seconds = 0
        hull_stats = defaultdict(int)
        
        current_session_start = None
        current_hull = "Unknown Ship"
        
        active_start = None
        active_hull = None

        for log in logs:
            if log.action == 'esi_join':
                # Close previous if exists (Edge case: missing leave event)
                if current_session_start:
                    duration = (log.timestamp - current_session_start).total_seconds()
                    if 0 < duration < 86400: # Ignore sessions > 24h as errors
                        total_seconds += duration
                        hull_stats[current_hull] += int(duration)

                # Start new session
                current_session_start = log.timestamp
                current_hull = log.ship_name or "Unknown Ship"
            
            elif log.action in ['ship_change', 'left_fleet', 'kicked'] and current_session_start:
                duration = (log.timestamp - current_session_start).total_seconds()
                
                if duration > 0:
                    total_seconds += duration
                    hull_stats[current_hull] += int(duration)
                
                if log.action == 'ship_change':
                    # Continue session with new ship
                    current_session_start = log.timestamp
                    current_hull = log.ship_name or "Unknown Ship"
                else:
                    # End session
                    current_session_start = None
                    current_hull = None

        # Check if currently active (last event was a join or ship change without a leave)
        # Note: 'logs' is ordered by timestamp, so we check the state after the loop
        if current_session_start:
            # Check how long ago it was. If > 12 hours, assume stale/broken session.
            time_since = timezone.now() - current_session_start
            if time_since.total_seconds() < 43200: # 12 hours
                active_start = current_session_start
                active_hull = current_hull
            else:
                # Close it out as a stale session
                total_seconds += time_since.total_seconds()
                hull_stats[current_hull] += int(time_since.total_seconds())

        # Update or Create Stats Row
        CharacterStats.objects.update_or_create(
            character=character,
            defaults={
                'total_seconds': int(total_seconds),
                'hull_stats': dict(hull_stats),
                'active_session_start': active_start,
                'active_hull': active_hull
            }
        )