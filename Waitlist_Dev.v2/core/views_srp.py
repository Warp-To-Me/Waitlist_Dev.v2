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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import get_template_base, get_mgmt_context
from pilot_data.models import SRPConfiguration, EveCharacter, CorpWalletJournal, EsiHeaderCache
from scheduler.tasks import refresh_srp_wallet_task
from esi_calls.wallet_service import get_corp_divisions

def can_manage_srp(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='manage_srp_source').exists()

def can_view_srp(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='view_srp_dashboard').exists()

# Helper decorator
def check_permission(perm_func):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not perm_func(request.user):
                return Response({'error': 'Permission Denied'}, status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

@api_view(['GET'])
@check_permission(can_manage_srp)
def srp_config(request):
    """
    Page to select which character provides SRP wallet data.
    """
    current_config = SRPConfiguration.objects.first()
    user_chars = request.user.characters.all()
    
    config_data = None
    if current_config and current_config.character:
        config_data = {
            'character_id': current_config.character.character_id,
            'character_name': current_config.character.character_name
        }
    
    chars_data = [{'character_id': c.character_id, 'character_name': c.character_name} for c in user_chars]

    return Response({
        'config': config_data,
        'user_chars': chars_data
    })

@api_view(['POST'])
@check_permission(can_manage_srp)
def api_set_srp_source(request):
    char_id = request.data.get('character_id')

    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    
    # Update or Create Singleton
    config, created = SRPConfiguration.objects.get_or_create(id=1, defaults={'character': character})
    if not created:
        config.character = character
        config.save()
        
    return Response({'success': True})

@api_view(['POST'])
@check_permission(can_manage_srp)
def api_sync_srp(request):
    """
    Triggers the background task via Celery.
    """
    config = SRPConfiguration.objects.first()
    if not config: return Response({'success': False, 'error': 'No configuration found'}, status=400)
    
    lock_key = f"srp_sync_lock_{config.id}"
    if cache.get(lock_key):
        return Response({'success': True, 'message': 'Sync already scheduled or in progress.'})

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
                countdown = int((cache_entry.expires - now).total_seconds())
                countdown += 5

    if countdown > 0:
        refresh_srp_wallet_task.apply_async(countdown=countdown)
        cache.set(lock_key, "queued", timeout=countdown + 30)
        msg = f"Sync scheduled in {countdown}s (respecting ESI cache)."
    else:
        refresh_srp_wallet_task.delay()
        cache.set(lock_key, "processing", timeout=60)
        msg = "Sync started immediately."
    
    return Response({'success': True, 'message': msg})

@api_view(['POST'])
@check_permission(can_manage_srp)
def api_update_transaction_category(request):
    """
    Updates the manual category for a specific wallet journal entry.
    """
    entry_id = request.data.get('entry_id')
    category = request.data.get('category')

    if not entry_id:
        return Response({'success': False, 'error': 'Entry ID required'}, status=400)

    # Get transaction (Using entry_id which is the unique ESI ID)
    transaction = get_object_or_404(CorpWalletJournal, entry_id=entry_id)
    
    # Update
    transaction.custom_category = category
    transaction.save()
    
    return Response({'success': True})

@api_view(['GET'])
@check_permission(can_manage_srp)
def api_divisions(request):
    """
    Fetches corp divisions from ESI.
    """
    config = SRPConfiguration.objects.first()
    if not config or not config.character:
        return Response({'error': 'No SRP Character Configured'}, status=400)

    divisions = get_corp_divisions(config.character)
    return Response(divisions)

# --- DASHBOARD ---

@api_view(['GET'])
@check_permission(can_view_srp)
def srp_dashboard(request):
    # Just a placeholder now, frontend logic fetches data separately
    # But we can return base config info if needed
    return Response({'status': 'active'})

@api_view(['GET'])
@check_permission(can_view_srp)
def api_srp_status(request):
    config = SRPConfiguration.objects.first()
    if not config:
        return Response({'active': False})

    next_sync = None
    if config.character and config.character.corporation_id:
        prefix = f"corp_wallet_{config.character.corporation_id}"
        cache_entry = EsiHeaderCache.objects.filter(
            character=config.character,
            endpoint_name__startswith=prefix
        ).order_by('-expires').first()
        
        if cache_entry and cache_entry.expires:
            next_sync = cache_entry.expires

    if not next_sync and config.last_sync:
        next_sync = config.last_sync + timedelta(hours=1)

    return Response({
        'active': True,
        'last_sync': config.last_sync.isoformat() if config.last_sync else None,
        'next_sync': next_sync.isoformat() if next_sync else None,
        'server_time': timezone.now().isoformat()
    })

@api_view(['GET'])
@check_permission(can_view_srp)
def api_srp_data(request):
    """
    Powerhouse API for the Dashboard Charts and Table.
    """
    config = SRPConfiguration.objects.first()
    if not config: return Response({'error': 'Not Configured'}, status=404)

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
        try:
            qs = qs.filter(division=int(f_div))
        except ValueError: pass

    if f_amount:
        if f_amount.startswith('>'):
            try: qs = qs.filter(amount__gt=float(f_amount[1:]))
            except: pass
        elif f_amount.startswith('<'):
            try: qs = qs.filter(amount__lt=float(f_amount[1:]))
            except: pass
        else:
            qs = qs.filter(amount__icontains=f_amount)

    if f_from: qs = qs.filter(first_party_name__icontains=f_from)
    if f_to: qs = qs.filter(second_party_name__icontains=f_to)
    if f_type: qs = qs.filter(ref_type__icontains=f_type)
    if f_category:
        if f_category == 'uncategorised':
            qs = qs.filter(Q(custom_category__isnull=True) | Q(custom_category=''))
        else:
            qs = qs.filter(custom_category__iexact=f_category)
    if f_reason: qs = qs.filter(reason__icontains=f_reason)

    # 3. Aggregates
    agg_qs = qs.exclude(custom_category='internal_transfer')
    total_income = agg_qs.filter(amount__gt=0).aggregate(s=Sum('amount'))['s'] or 0
    total_outcome = agg_qs.filter(amount__lt=0).aggregate(s=Sum('amount'))['s'] or 0
    net_change = total_income + total_outcome

    # 4. Division Balances
    div_balances = {}
    if divisions:
        for div_id in divisions:
            latest_entry = CorpWalletJournal.objects.filter(
                config=config, 
                division=div_id
            ).order_by('-entry_id').values('balance').first()
            div_balances[div_id] = latest_entry['balance'] if latest_entry else 0

    # 5. Process Data for Charts
    chart_data = qs.values('amount', 'date', 'ref_type', 'first_party_name', 'second_party_name', 'custom_category').order_by('date')
    
    monthly_stats = {}
    top_payers = {}
    ref_type_breakdown = {'in': {}, 'out': {}}
    timeline_payers = {}

    for row in chart_data:
        amt = float(row['amount'])
        d = row['date']
        month_key = f"{d.year}-{d.month:02d}"
        
        # Prepare Label First
        category_label = row['custom_category']
        if not category_label:
            category_label = row['ref_type'].replace('_', ' ').title()
        else:
            category_label = category_label.replace('_', ' ').title()

        # Monthly Stats: Store granular breakdown for frontend filtering
        if month_key not in monthly_stats: monthly_stats[month_key] = {}
        monthly_stats[month_key][category_label] = monthly_stats[month_key].get(category_label, 0) + amt

        if amt > 0:
            ref_type_breakdown['in'][category_label] = ref_type_breakdown['in'].get(category_label, 0) + amt
        else:
            ref_type_breakdown['out'][category_label] = ref_type_breakdown['out'].get(category_label, 0) + abs(amt)

        if row['ref_type'] == 'player_donation' and amt > 0:
            payer = row['first_party_name']
            if payer not in top_payers: top_payers[payer] = {'count': 0, 'total': 0}
            top_payers[payer]['count'] += 1
            top_payers[payer]['total'] += amt
            
            day_key = d.strftime("%Y-%m-%d")
            if payer not in timeline_payers: timeline_payers[payer] = {}
            timeline_payers[payer][day_key] = timeline_payers[payer].get(day_key, 0) + amt

    # 5. Transaction Table
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

    return Response({
        'summary': {
            'income': total_income,
            'outcome': total_outcome,
            'net': net_change
        },
        'division_balances': div_balances,
        'monthly': monthly_stats,
        'categories': ref_type_breakdown,
        'top_payers': top_payers,
        'timeline': timeline_payers,
        'transactions': paginated_transactions,
        'pagination': pagination_meta
    })