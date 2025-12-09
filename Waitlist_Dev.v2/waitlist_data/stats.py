from collections import defaultdict
from django.utils import timezone
from .models import FleetActivity

def calculate_pilot_stats(character):
    """
    Single character wrapper for the batch logic.
    """
    results = batch_calculate_pilot_stats([character.character_id])
    return results.get(character.character_id, _get_empty_stats())

def batch_calculate_pilot_stats(character_ids):
    """
    Efficiently calculates stats for multiple characters in one DB query.
    Returns: { char_id: { 'total_seconds': int, 'hull_stats': { 'Megathron': 120 }, ... } }
    """
    if not character_ids:
        return {}

    # FIX: Filter by 'character__character_id' (EVE ID) not 'character_id' (Row FK)
    # We also select_related('character') to group by the actual EVE ID efficiently
    logs = FleetActivity.objects.filter(character__character_id__in=character_ids)\
        .select_related('character')\
        .order_by('character__character_id', 'timestamp')
    
    # Group logs by character EVE ID
    char_logs = defaultdict(list)
    for log in logs:
        char_logs[log.character.character_id].append(log)

    results = {}
    
    for char_id in character_ids:
        if char_id not in char_logs:
            results[char_id] = _get_empty_stats()
            continue

        c_logs = char_logs[char_id]
        total_seconds = 0
        hull_stats = defaultdict(int)
        
        current_session_start = None
        current_hull = None
        
        active_session_start = None
        active_hull = None

        for log in c_logs:
            if log.action == 'esi_join':
                # FIX: If we are already in a session, close the previous segment before starting new one.
                # This handles cases where the server restarts or audits re-detect the user.
                if current_session_start:
                    duration = (log.timestamp - current_session_start).total_seconds()
                    # Sanity check: ignore overlapping segments > 24h just in case
                    if 0 < duration < 86400:
                        total_seconds += duration
                        hull_stats[current_hull] += duration

                current_session_start = log.timestamp
                current_hull = log.ship_name or "Unknown Ship"
            
            elif log.action in ['ship_change', 'left_fleet', 'kicked'] and current_session_start:
                duration = (log.timestamp - current_session_start).total_seconds()
                
                if duration > 0:
                    total_seconds += duration
                    hull_stats[current_hull] += duration
                
                if log.action == 'ship_change':
                    current_session_start = log.timestamp
                    current_hull = log.ship_name or "Unknown Ship"
                else:
                    current_session_start = None
                    current_hull = None

        # Handle Active Session (still logged in)
        if current_session_start:
            now = timezone.now()
            duration = (now - current_session_start).total_seconds()
            if duration < 43200: # 12h cap sanity check for active sessions
                total_seconds += duration
                hull_stats[current_hull] += duration
                
                active_session_start = current_session_start
                active_hull = current_hull

        results[char_id] = {
            'total_seconds': total_seconds,
            'total_hours': round(total_seconds / 3600, 1),
            'hull_breakdown': dict(hull_stats), # Convert from defaultdict
            'active_session_start': active_session_start,
            'active_hull': active_hull
        }

    return results

def _get_empty_stats():
    return {
        'total_seconds': 0, 
        'total_hours': 0.0, 
        'hull_breakdown': {},
        'active_session_start': None,
        'active_hull': None
    }