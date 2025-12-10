import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum
from dateutil.parser import parse

from core.permissions import get_template_base, get_mgmt_context
from pilot_data.models import SRPConfiguration, EveCharacter, CorpWalletJournal
from scheduler.tasks import refresh_srp_wallet_task # Import the task

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
    
    # FIRE AND FORGET
    refresh_srp_wallet_task.delay()
    
    return JsonResponse({'success': True, 'message': 'Sync started in background. Check back in a few minutes.'})

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
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'srp/dashboard.html', context)

@login_required
@user_passes_test(can_view_srp)
def api_srp_data(request):
    """
    Powerhouse API for the Dashboard Charts and Table.
    """
    config = SRPConfiguration.objects.first()
    if not config: return JsonResponse({'error': 'Not Configured'}, status=404)

    # 1. Filters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    divisions = request.GET.getlist('divisions[]') # List of ints
    
    qs = CorpWalletJournal.objects.filter(config=config)
    
    if start_date_str: qs = qs.filter(date__gte=parse(start_date_str))
    if end_date_str: qs = qs.filter(date__lte=parse(end_date_str))
    if divisions: qs = qs.filter(division__in=divisions)

    # 2. Aggregates (Income/Outcome)
    total_income = qs.filter(amount__gt=0).aggregate(s=Sum('amount'))['s'] or 0
    total_outcome = qs.filter(amount__lt=0).aggregate(s=Sum('amount'))['s'] or 0
    net_change = total_income + total_outcome

    # 3. Process Data for Charts
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

    # 4. Transaction Table (Limit 500)
    # Added entry_id and custom_category
    recent_transactions = list(qs.order_by('-date')[:500].values(
        'entry_id', 'date', 'division', 'amount', 'first_party_name', 
        'second_party_name', 'ref_type', 'reason', 'custom_category'
    ))

    return JsonResponse({
        'summary': {
            'income': total_income,
            'outcome': total_outcome,
            'net': net_change
        },
        'monthly': monthly_stats,
        'categories': ref_type_breakdown,
        'top_payers': top_payers,
        'timeline': timeline_payers,
        'transactions': recent_transactions
    })