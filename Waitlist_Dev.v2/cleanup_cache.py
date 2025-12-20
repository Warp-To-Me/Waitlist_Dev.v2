import os
import django
import sys

# Setup Django Environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'waitlist_project.settings')
django.setup()

from pilot_data.models import EsiHeaderCache

def cleanup():
    print("Starting Cleanup...")

    # 1. Fleet Endpoints
    fleet_rows = EsiHeaderCache.objects.filter(endpoint_name__startswith='fleet_')
    count_fleet = fleet_rows.count()
    if count_fleet > 0:
        print(f"Deleting {count_fleet} fleet_ cache entries...")
        fleet_rows.delete()
    else:
        print("No fleet_ entries found.")

    # 2. Online Endpoints (Legacy)
    online_rows = EsiHeaderCache.objects.filter(endpoint_name='online')
    count_online = online_rows.count()
    if count_online > 0:
        print(f"Deleting {count_online} 'online' cache entries...")
        online_rows.delete()
    else:
        print("No 'online' entries found.")

    print("Cleanup Complete.")

if __name__ == "__main__":
    cleanup()
