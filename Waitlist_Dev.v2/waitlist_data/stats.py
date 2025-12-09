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

    logs = FleetActivity.objects.filter(character_id__in=character_ids).order_by('character_id', 'timestamp')
    
    # Group logs by character
    char_logs = defaultdict(list)
    for log in logs:
        char_logs[log.character_id].append(log)

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
                current_session_start = log.timestamp
                current_hull = log.ship_name or "Unknown Ship"
            
            elif log.action in ['ship_change', 'left_fleet', 'kicked'] and current_session_start:
                duration = (log.timestamp - current_session_start).total_seconds()
                total_seconds += duration
                hull_stats[current_hull] += duration
                
                if log.action == 'ship_change':
                    current_session_start = log.timestamp
                    current_hull = log.ship_name or "Unknown Ship"
                else:
                    current_session_start = None
                    current_hull = None

        # Handle Active Session
        if current_session_start:
            now = timezone.now()
            duration = (now - current_session_start).total_seconds()
            if duration < 43200: # 12h cap sanity check
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