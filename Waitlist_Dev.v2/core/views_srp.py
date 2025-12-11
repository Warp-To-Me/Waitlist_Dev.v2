import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from django.core.cache import cache # Import Cache
from django.utils import timezone
from datetime import timedelta
from dateutil.parser import parse

from core.permissions import get_template_base, get_mgmt_context
from pilot_data.models import SRPConfiguration, EveCharacter, CorpWalletJournal, EsiHeaderCache
from scheduler.tasks import refresh_srp_wallet_task

def can_manage_srp(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='manage_srp_source').exists()

def can_view_srp(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='view_srp_dashboard').exists()

@login_required
@user_passes_test(can_manage_srp)
def srp_config(request):
    """
    Page to select which character provides SRP wallet data.
    """
    current_config = SRPConfiguration.objects.first()
    user_chars = request.user.characters.all()
    
    context = {
        'config': current_config,
        'user_chars': user_chars,
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/srp_config.html', context)

@login_required
@user_passes_test(can_manage_srp)
@require_POST
def api_set_srp_source(request):
    try:
        data = json.loads(request.body)
        char_id = data.get('character_id')
    except json.JSONDecodeError: return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    
    # Update or Create Singleton
    config, created = SRPConfiguration.objects.get_or_create(id=1, defaults={'character': character})
    if not created:
        config.character = character
        config.save()
        
    return JsonResponse({'success': True})

@login_required
@user_passes_test(can_manage_srp)
@require_POST
def api_sync_srp(request):
    """
    Triggers the background task via Celery.
    Returns immediately so the UI doesn't freeze.
    """
    config = SRPConfiguration.objects.first()
    if not config: return JsonResponse({'success': False, 'error': 'No configuration found'})
    
    # 1. Debounce Check: Prevent spamming the button
    # If a sync is already queued/running for this config, block the request.
    lock_key = f"srp_sync_lock_{config.id}"
    if cache.get(lock_key):
        return JsonResponse({'success': True, 'message': 'Sync already scheduled or in progress.'})

    # Determine execution time based on ESI Cache
    countdown = 0
    if config.character and config.character.corporation_id:
        prefix = f"corp_wallet_{config.character.corporation_id}"
        cache_entry = EsiHeaderCache.objects.filter(
            character=config.character,
            endpoint_name__startswith=prefix
        ).order_by('-expires').first()
        
        if cache_entry and cache_entry.expires:
            now = timezone.now()
            if cache_entry.expires > now:
                # Calculate seconds until expiry
                countdown = int((cache_entry.expires - now).total_seconds())
                # Add a small buffer (e.g. 5 seconds) to ensure ESI has updated
                countdown += 5

    # 2. Schedule Task & Set Lock
    if countdown > 0:
        refresh_srp_wallet_task.apply_async(countdown=countdown)
        
        # Lock for the duration of the wait + 30s for execution time
        cache.set(lock_key, "queued", timeout=countdown + 30)
        
        msg = f"Sync scheduled in {countdown}s (respecting ESI cache)."
    else:
        # Immediate execution
        refresh_srp_wallet_task.delay()
        
        # Lock for 60 seconds to prevent rapid-fire clicking
        cache.set(lock_key, "processing", timeout=60)
        
        msg = "Sync started immediately."
    
    return JsonResponse({'success': True, 'message': msg})

@login_required
@user_passes_test(can_manage_srp)
@require_POST
def api_update_transaction_category(request):
    """
    Updates the manual category for a specific wallet journal entry.
    """
    try:
        data = json.loads(request.body)
        entry_id = data.get('entry_id')
        category = data.get('category')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    if not entry_id:
        return JsonResponse({'success': False, 'error': 'Entry ID required'})

    # Get transaction (Using entry_id which is the unique ESI ID)
    transaction = get_object_or_404(CorpWalletJournal, entry_id=entry_id)
    
    # Update
    transaction.custom_category = category
    transaction.save()
    
    return JsonResponse({'success': True})

# --- DASHBOARD ---

@login_required
@user_passes_test(can_view_srp)
def srp_dashboard(request):
    config = SRPConfiguration.objects.first()
    
    context = {
        'config': config,
        # 'next_sync' is now fetched via API to ensure client-side freshness
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'srp/dashboard.html', context)

@login_required
@user_passes_test(can_view_srp)
def api_srp_status(request):
    """
    Lightweight endpoint for polling Sync Status (Last Sync / Next Sync).
    """
    config = SRPConfiguration.objects.first()
    if not config:
        return JsonResponse({'active': False})

    next_sync = None
    if config.character and config.character.corporation_id:
        # Matches format in wallet_service.py: corp_wallet_{id}_{div}_{page}
        prefix = f"corp_wallet_{config.character.corporation_id}"
        
        cache_entry = EsiHeaderCache.objects.filter(
            character=config.character,
            endpoint_name__startswith=prefix
        ).order_by('-expires').first()
        
        if cache_entry and cache_entry.expires:
            next_sync = cache_entry.expires

    # Fallback to 1 hour if no cache headers found
    if not next_sync and config.last_sync:
        next_sync = config.last_sync + timedelta(hours=1)

    return JsonResponse({
        'active': True,
        'last_sync': config.last_sync.isoformat() if config.last_sync else None,
        'next_sync': next_sync.isoformat() if next_sync else None,
        'server_time': timezone.now().isoformat()
    })

@login_required
@user_passes_test(can_view_srp)
def api_srp_data(request):
    """
    Powerhouse API for the Dashboard Charts and Table.
    """
    config = SRPConfiguration.objects.first()
    if not config: return JsonResponse({'error': 'Not Configured'}, status=404)

    # 1. Base Filters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    divisions = request.GET.getlist('divisions[]') # List of ints
    
    # 2. Text/Search Filters (NEW)
    f_div = request.GET.get('f_div', '').strip()   # NEW
    f_amount = request.GET.get('f_amount', '').strip()
    f_from = request.GET.get('f_from', '').strip() # Renamed from f_party
    f_to = request.GET.get('f_to', '').strip()     # New 'To' filter
    f_type = request.GET.get('f_type', '').strip()
    f_category = request.GET.get('f_category', '').strip()
    f_reason = request.GET.get('f_reason', '').strip()

    # Pagination Params
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
        
    try:
        limit = int(request.GET.get('limit', 25))
    except ValueError:
        limit = 25
    
    qs = CorpWalletJournal.objects.filter(config=config)
    
    # Apply Base Filters
    if start_date_str: qs = qs.filter(date__gte=parse(start_date_str))
    if end_date_str: qs = qs.filter(date__lte=parse(end_date_str))
    if divisions: qs = qs.filter(division__in=divisions)

    # Apply Column Search Filters
    if f_div:
        # Strict exact match for division number
        try:
            qs = qs.filter(division=int(f_div))
        except ValueError:
            pass # Ignore invalid non-integer searches

    if f_amount:
        if f_amount.startswith('>'):
            try: qs = qs.filter(amount__gt=float(f_amount[1:]))
            except: pass
        elif f_amount.startswith('<'):
            try: qs = qs.filter(amount__lt=float(f_amount[1:]))
            except: pass
        else:
            qs = qs.filter(amount__icontains=f_amount) # String match fallback

    # Changed: Split party filter into From and To
    if f_from:
        qs = qs.filter(first_party_name__icontains=f_from)
        
    if f_to:
        qs = qs.filter(second_party_name__icontains=f_to)
    
    if f_type:
        qs = qs.filter(ref_type__icontains=f_type)
        
    if f_category:
        if f_category == 'uncategorised':
            # Filter for NULL or Empty string
            qs = qs.filter(Q(custom_category__isnull=True) | Q(custom_category=''))
        else:
            qs = qs.filter(custom_category__iexact=f_category)
        
    if f_reason:
        # Standard contains search (Removed [empty] token logic)
        qs = qs.filter(reason__icontains=f_reason)

    # 3. Aggregates (Income/Outcome) - CALCULATED ON FULL SET (POST-FILTER)
    # Exclude internal transfers from these specific totals per user request
    agg_qs = qs.exclude(custom_category='internal_transfer')
    total_income = agg_qs.filter(amount__gt=0).aggregate(s=Sum('amount'))['s'] or 0
    total_outcome = agg_qs.filter(amount__lt=0).aggregate(s=Sum('amount'))['s'] or 0
    net_change = total_income + total_outcome

    # 4. Division Balances (Snapshot of latest known state)
    # We fetch the absolute latest entry for each selected division, ignoring date filters
    div_balances = {}
    if divisions:
        for div_id in divisions:
            # FIX: Order by entry_id DESC primarily. Date can be unreliable for same-tick transactions.
            # ESI entry_id is strictly sequential.
            latest_entry = CorpWalletJournal.objects.filter(
                config=config, 
                division=div_id
            ).order_by('-entry_id').values('balance').first()
            
            if latest_entry:
                div_balances[div_id] = latest_entry['balance']
            else:
                div_balances[div_id] = 0

    # 5. Process Data for Charts - CALCULATED ON FULL SET (POST-FILTER)
    chart_data = qs.values('amount', 'date', 'ref_type', 'first_party_name', 'second_party_name', 'custom_category').order_by('date')
    
    monthly_stats = {}
    top_payers = {}
    ref_type_breakdown = {'in': {}, 'out': {}}
    timeline_payers = {}

    for row in chart_data:
        amt = float(row['amount'])
        d = row['date']
        month_key = f"{d.year}-{d.month:02d}"
        
        # Monthly
        if month_key not in monthly_stats: monthly_stats[month_key] = {'in': 0, 'out': 0}
        if amt > 0: monthly_stats[month_key]['in'] += amt
        else: monthly_stats[month_key]['out'] += abs(amt)

        # Ref Types (Prefer custom category if set)
        category_label = row['custom_category']
        if not category_label:
            category_label = row['ref_type'].replace('_', ' ').title()
        else:
            category_label = category_label.replace('_', ' ').title()

        if amt > 0:
            ref_type_breakdown['in'][category_label] = ref_type_breakdown['in'].get(category_label, 0) + amt
        else:
            ref_type_breakdown['out'][category_label] = ref_type_breakdown['out'].get(category_label, 0) + abs(amt)

        # Payers
        if row['ref_type'] == 'player_donation' and amt > 0:
            payer = row['first_party_name']
            if payer not in top_payers: top_payers[payer] = {'count': 0, 'total': 0}
            top_payers[payer]['count'] += 1
            top_payers[payer]['total'] += amt
            
            day_key = d.strftime("%Y-%m-%d")
            if payer not in timeline_payers: timeline_payers[payer] = {}
            timeline_payers[payer][day_key] = timeline_payers[payer].get(day_key, 0) + amt

    # 5. Transaction Table (Paginated)
    full_qs = qs.order_by('-date')
    paginator = Paginator(full_qs, limit)
    page_obj = paginator.get_page(page_number)

    paginated_transactions = list(page_obj.object_list.values(
        'entry_id', 'date', 'division', 'amount', 'first_party_name', 
        'second_party_name', 'ref_type', 'reason', 'custom_category'
    ))

    pagination_meta = {
        'current_page': page_obj.number,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'total_count': paginator.count,
        'limit': limit
    }

    return JsonResponse({
        'summary': {
            'income': total_income,
            'outcome': total_outcome,
            'net': net_change
        },
        'division_balances': div_balances, # NEW FIELD
        'monthly': monthly_stats,
        'categories': ref_type_breakdown,
        'top_payers': top_payers,
        'timeline': timeline_payers,
        'transactions': paginated_transactions,
        'pagination': pagination_meta
    })