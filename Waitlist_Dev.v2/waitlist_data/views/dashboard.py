from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from collections import defaultdict
import requests 

from core.permissions import (
    get_template_base, 
    is_fleet_command, 
    can_view_fleet_overview,
    get_mgmt_context
)
from pilot_data.models import EveCharacter, ItemType
from waitlist_data.models import Fleet, WaitlistEntry, FleetActivity, DoctrineCategory
from waitlist_data.stats import batch_calculate_pilot_stats
from esi_calls.fleet_service import get_fleet_composition, process_fleet_data, ESI_BASE
from esi_calls.token_manager import check_token
from .helpers import _resolve_column, get_category_map, get_entry_target_column, get_entry_real_category
from core.decorators import check_ban_status

@login_required
@check_ban_status
def fleet_dashboard(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    fc_name = EveCharacter.objects.filter(user=fleet.commander, is_main=True).values_list('character_name', flat=True).first()
    if not fc_name:
        fc_name = EveCharacter.objects.filter(user=fleet.commander).values_list('character_name', flat=True).first()
    if not fc_name:
        fc_name = fleet.commander.username

    # Fetch Entries
    entries = WaitlistEntry.objects.filter(fleet=fleet).exclude(status__in=['rejected', 'left']).select_related(
        'character', 'fit', 'fit__ship_type', 'fit__category', 'hull'
    ).order_by('created_at')

    # Calculate Stats
    char_ids = [e.character.character_id for e in entries]
    all_stats = batch_calculate_pilot_stats(char_ids)
    
    # Prep columns
    columns = {'pending': [], 'logi': [], 'dps': [], 'sniper': [], 'other': []}
    
    # Get lightweight category map for column resolution
    category_map = get_category_map()

    # --- PASS 1: Resolve Columns & Build Pilot Map ---
    char_columns = defaultdict(set) # char_id -> set of active columns
    
    processed_entries = []
    
    for entry in entries:
        # Determine stats
        stats = all_stats.get(entry.character.character_id, {})
        hull_name = entry.hull.type_name if entry.hull else "Unknown"
        hull_seconds = stats.get('hull_breakdown', {}).get(hull_name, 0)
        
        entry.display_stats = {
            'total_hours': stats.get('total_hours', 0),
            'hull_hours': round(hull_seconds / 3600, 1)
        }

        # Resolve Target Column (Visual)
        target_visual = get_entry_target_column(entry, category_map)
        entry.target_column = target_visual 
        
        # Resolve REAL Category (For Indicators)
        real_cat = get_entry_real_category(entry, category_map)
        entry.real_category = real_cat
        
        # Track for Multi-Fit Indicators
        # We track the REAL category so pending entries still contribute their role info
        if real_cat in ['logi', 'dps', 'sniper']:
            char_columns[entry.character.character_id].add(real_cat)
            
        processed_entries.append(entry)

    # --- PASS 2: Assign Indicators & Populate Lists ---
    for entry in processed_entries:
        # Calculate other categories for this pilot
        all_pilot_cats = char_columns.get(entry.character.character_id, set())
        
        # Exclude the current card's REAL category from its own indicators
        # This prevents a pending Logi fit from showing a Logi dot on itself
        entry.other_categories = list(all_pilot_cats - {entry.real_category})
        
        # Add to view list based on visual column
        if entry.target_column in columns:
            columns[entry.target_column].append(entry)
        else:
            columns['other'].append(entry)

    # --- User Characters (for X-Up Modal) ---
    user_chars = request.user.characters.filter(x_up_visible=True).prefetch_related('implants')
    
    implant_type_ids = set()
    for char in user_chars:
        for imp in char.implants.all():
            implant_type_ids.add(imp.type_id)
            
    item_map = ItemType.objects.filter(type_id__in=implant_type_ids).in_bulk(field_name='type_id')
    
    for char in user_chars:
        char.active_implants = []
        for imp in char.implants.all():
            item = item_map.get(imp.type_id)
            if item:
                char.active_implants.append({
                    'name': item.type_name,
                    'id': item.type_id
                })

    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related('subcategories__fits')
    can_view_overview = can_view_fleet_overview(request.user)

    context = {
        'fleet': fleet,
        'fc_name': fc_name,
        'columns': columns,
        'user_chars': user_chars,
        'categories': categories,
        'is_fc': is_fleet_command(request.user),
        'is_commander': request.user == fleet.commander,
        'can_view_overview': can_view_overview,
        'base_template': get_template_base(request)
    }
    return render(request, 'waitlist/dashboard.html', context)

@login_required
def fleet_history_view(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    
    if not is_fleet_command(request.user):
        return render(request, 'access_denied.html', {'base_template': get_template_base(request)})

    logs = FleetActivity.objects.filter(fleet=fleet).select_related('character', 'actor', 'character__user').order_by('-timestamp')
    
    total_xups = logs.filter(action='x_up').count()
    total_kills = logs.filter(action__in=['denied', 'kicked']).count()
    unique_pilots = logs.values('character').distinct().count()
    
    context = {
        'fleet': fleet,
        'logs': logs,
        'stats': {
            'xups': total_xups,
            'removals': total_kills,
            'pilots': unique_pilots
        },
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/history.html', context)

@login_required
def fleet_overview_api(request, token):
    fleet = get_object_or_404(Fleet, join_token=token)
    if not fleet.commander: return JsonResponse({'error': 'No commander'}, status=404)
    fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
    if not fc_char: return JsonResponse({'error': 'FC has no characters'}, status=400)
    actual_fleet_id = fleet.esi_fleet_id
    if not actual_fleet_id:
        if check_token(fc_char):
            headers = {'Authorization': f'Bearer {fc_char.access_token}'}
            try:
                resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    actual_fleet_id = data['fleet_id']
                    fleet.esi_fleet_id = actual_fleet_id
                    fleet.save()
            except Exception: pass
    if not actual_fleet_id: return JsonResponse({'error': 'No ESI Fleet'}, status=404)
    composite_data, _ = get_fleet_composition(actual_fleet_id, fc_char)
    if composite_data is None: return JsonResponse({'error': 'ESI Fail'}, status=500)
    elif composite_data == 'unchanged': return JsonResponse({'status': 'unchanged'}, status=200)
    summary, hierarchy = process_fleet_data(composite_data)
    return JsonResponse({'fleet_id': actual_fleet_id, 'member_count': len(composite_data.get('members', [])), 'summary': summary, 'hierarchy': hierarchy})