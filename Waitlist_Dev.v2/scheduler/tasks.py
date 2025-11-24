from django.utils import timezone
from datetime import timedelta
from pilot_data.models import EveCharacter
from esi_calls.token_manager import update_character_data

def background_token_refresh():
    """
    Finds characters with stale data and refreshes them via ESI.
    Uses the refresh token to get a new access token if needed.
    """
    # Define 'Stale': Not updated in the last 60 minutes
    threshold = timezone.now() - timedelta(minutes=60)
    
    # Find characters that need updating
    stale_characters = EveCharacter.objects.filter(last_updated__lt=threshold)
    
    count = stale_characters.count()
    if count > 0:
        print(f"[Scheduler] Found {count} stale characters. Starting refresh cycle...")
        
        success_count = 0
        for char in stale_characters:
            try:
                # update_character_data handles the token refresh automatically 
                # via check_token() inside esi_calls/token_manager.py
                result = update_character_data(char)
                if result:
                    success_count += 1
                    print(f" - Refreshed: {char.character_name}")
                else:
                    print(f" - Failed: {char.character_name}")
            except Exception as e:
                print(f" - Error processing {char.character_name}: {e}")
                
        print(f"[Scheduler] Cycle complete. Updated {success_count}/{count} characters.")
    else:
        print("[Scheduler] No stale characters found.")