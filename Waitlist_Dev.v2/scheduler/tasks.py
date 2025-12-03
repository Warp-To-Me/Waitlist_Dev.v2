from django.utils import timezone
from datetime import timedelta
from pilot_data.models import EveCharacter
from esi_calls.token_manager import update_character_data
import time

def background_token_refresh():
    """
    Finds characters with stale data and refreshes them via ESI.
    Uses the refresh token to get a new access token if needed.
    """
    # Define 'Stale': Not updated in the last 60 minutes
    threshold = timezone.now() - timedelta(minutes=60)
    
    # Find characters that need updating
    # LIMIT the batch size to 50 to prevent API timeouts or rate limits if the queue is huge.
    # We order by 'last_updated' to prioritize those waiting the longest.
    stale_characters = EveCharacter.objects.filter(last_updated__lt=threshold).order_by('last_updated')[:50]
    
    count = stale_characters.count()
    if count > 0:
        print(f"[Scheduler] Found {count} stale characters (Batch Limit: 50). Starting refresh cycle...")
        
        success_count = 0
        for char in stale_characters:
            try:
                # Update ESI Data
                result = update_character_data(char)
                
                if result:
                    success_count += 1
                    print(f" - Refreshed: {char.character_name}")
                else:
                    print(f" - Failed: {char.character_name}")
                    # CRITICAL: Touch 'last_updated' even on failure.
                    # This prevents the scheduler from retrying the same broken character 
                    # every 15 minutes forever. It pushes them to the back of the queue.
                    char.save() 
                    
                # Polite sleep to avoid hammering ESI too hard in a loop
                time.sleep(0.1)

            except Exception as e:
                print(f" - Error processing {char.character_name}: {e}")
                # Touch timestamp on crash to prevent infinite loop
                char.save()
                
        print(f"[Scheduler] Cycle complete. Updated {success_count}/{count} characters.")
    else:
        print("[Scheduler] No stale characters found.")