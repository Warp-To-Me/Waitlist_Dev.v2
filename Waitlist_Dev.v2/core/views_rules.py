import json
import base64
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count
from django.db import transaction

# Core
from core.permissions import can_manage_analysis_rules, get_mgmt_context, get_template_base

# Models
from pilot_data.models import ItemGroup, ItemType, TypeAttribute, AttributeDefinition, FitAnalysisRule

@login_required
@user_passes_test(can_manage_analysis_rules)
def management_rules(request):
    """
    Renders the Rule Helper Dashboard.
    """
    context = {
        'base_template': get_template_base(request)
    }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/rules_helper.html', context)

@login_required
@user_passes_test(can_manage_analysis_rules)
def api_group_search(request):
    """
    Searches for ItemGroups (e.g. "Shield Hardener")
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 3: 
        # Return first 20 module groups (Category 7 = Module)
        groups = ItemGroup.objects.filter(category_id=7, published=True).order_by('group_name')[:20]
    else:
        groups = ItemGroup.objects.filter(group_name__icontains=query, published=True)[:20]
        
    results = [{'id': g.group_id, 'name': g.group_name} for g in groups]
    return JsonResponse({'results': results})

@login_required
@user_passes_test(can_manage_analysis_rules)
def api_rule_discovery(request, group_id):
    """
    The Brains:
    1. Fetches existing saved rules for this group.
    2. Scans items in this group to find 'Candidate' attributes.
    """
    group = get_object_or_404(ItemGroup, group_id=group_id)
    
    # 1. Get Existing Rules
    existing_rules = FitAnalysisRule.objects.filter(group=group).select_related('attribute')
    existing_attr_ids = set()
    rule_data = []
    
    for r in existing_rules:
        existing_attr_ids.add(r.attribute.attribute_id)
        rule_data.append({
            'attr_id': r.attribute.attribute_id,
            'name': r.attribute.display_name or r.attribute.name,
            'description': r.attribute.description,
            'is_active': True,
            'logic': r.comparison_logic,
            'tolerance': r.tolerance_percent,
            'source': 'saved'
        })

    # 2. Discover Candidates
    sample_items = ItemType.objects.filter(group_id=group.group_id, published=True)[:10]
    sample_ids = list(sample_items.values_list('type_id', flat=True))
    
    if not sample_ids:
        # Fallback: Try finding unpublished items
        unpublished = ItemType.objects.filter(group_id=group.group_id).count()
        if unpublished > 0:
            sample_ids = list(ItemType.objects.filter(group_id=group.group_id)[:10].values_list('type_id', flat=True))

    if sample_ids:
        common_attrs = TypeAttribute.objects.filter(item_id__in=sample_ids)\
            .values('attribute_id')\
            .annotate(count=Count('item_id'))\
            .order_by('-count')
            
        # Filter for attributes that appear in at least 50% of the sample
        threshold = len(sample_ids) / 2
        candidate_ids = [c['attribute_id'] for c in common_attrs if c['count'] >= threshold]
        
        # Remove ones we already have rules for
        new_ids = [aid for aid in candidate_ids if aid not in existing_attr_ids]
        
        # Fetch definitions
        definitions = AttributeDefinition.objects.filter(attribute_id__in=new_ids)
        
        for d in definitions:
            if any(x in d.name.lower() for x in ['graphic', 'icon', 'sound', 'radius', 'volume', 'mass', 'capacity']):
                continue
                
            rule_data.append({
                'attr_id': d.attribute_id,
                'name': d.display_name or d.name,
                'description': d.description,
                'is_active': False,
                'logic': 'higher',
                'tolerance': 0.0,
                'source': 'discovery'
            })

    rule_data.sort(key=lambda x: (not x['is_active'], x['name']))
    
    return JsonResponse({
        'group_id': group.group_id,
        'group_name': group.group_name,
        'rules': rule_data
    })

@login_required
@user_passes_test(can_manage_analysis_rules)
@require_POST
def api_save_rules(request):
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        rules_payload = data.get('rules', [])
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    group = get_object_or_404(ItemGroup, group_id=group_id)
    
    with transaction.atomic():
        FitAnalysisRule.objects.filter(group=group).delete()
        new_objects = []
        for r in rules_payload:
            attr = AttributeDefinition.objects.get(attribute_id=r['attr_id'])
            new_objects.append(FitAnalysisRule(
                group=group,
                attribute=attr,
                comparison_logic=r['logic'],
                tolerance_percent=float(r.get('tolerance', 0.0))
            ))
        FitAnalysisRule.objects.bulk_create(new_objects)
        
    return JsonResponse({'success': True, 'count': len(new_objects)})

@login_required
@user_passes_test(can_manage_analysis_rules)
def api_list_configured_groups(request):
    groups_qs = FitAnalysisRule.objects.values('group__group_id', 'group__group_name')\
        .annotate(rule_count=Count('id'))\
        .order_by('group__group_name')
    
    query = request.GET.get('q', '').strip()
    if query:
        groups_qs = groups_qs.filter(group__group_name__icontains=query)

    page_number = request.GET.get('page', 1)
    paginator = Paginator(groups_qs, 20)
    page_obj = paginator.get_page(page_number)
    
    results = [
        {'id': g['group__group_id'], 'name': g['group__group_name'], 'count': g['rule_count']}
        for g in page_obj
    ]
    
    return JsonResponse({
        'results': results,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'current_page': page_obj.number,
        'total_pages': paginator.num_pages
    })

@login_required
@user_passes_test(can_manage_analysis_rules)
@require_POST
def api_delete_rules(request):
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})

    if not group_id:
        return JsonResponse({'success': False, 'error': 'Group ID required'})

    group = get_object_or_404(ItemGroup, group_id=group_id)
    deleted_count, _ = FitAnalysisRule.objects.filter(group=group).delete()
    return JsonResponse({'success': True, 'deleted': deleted_count})

@login_required
@user_passes_test(can_manage_analysis_rules)
def api_export_rules(request):
    rules = FitAnalysisRule.objects.select_related('group', 'attribute').all().order_by('group__group_name')
    export_data = []
    
    for r in rules:
        export_data.append({
            'group_id': r.group.group_id,
            'group_name': r.group.group_name,
            'attr_id': r.attribute.attribute_id,
            'attr_name': r.attribute.name,
            'logic': r.comparison_logic,
            'tolerance': r.tolerance_percent,
            'priority': r.priority
        })
        
    json_str = json.dumps(export_data)
    encoded_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    return JsonResponse({'success': True, 'export_string': encoded_str, 'count': len(export_data)})

@login_required
@user_passes_test(can_manage_analysis_rules)
@require_POST
def api_import_rules(request):
    try:
        data = json.loads(request.body)
        import_string = data.get('import_string', '')
        
        if not import_string:
            return JsonResponse({'success': False, 'error': 'Empty import string.'})
            
        try:
            json_bytes = base64.b64decode(import_string)
            rules_list = json.loads(json_bytes.decode('utf-8'))
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid Base64 or JSON format.'})
            
        if not isinstance(rules_list, list):
            return JsonResponse({'success': False, 'error': 'Invalid data structure (expected list).'})

        created_count = 0
        missing_sde_count = 0
        
        with transaction.atomic():
            FitAnalysisRule.objects.all().delete()
            new_rules = []
            
            valid_group_ids = set(ItemGroup.objects.values_list('group_id', flat=True))
            valid_attr_ids = set(AttributeDefinition.objects.values_list('attribute_id', flat=True))
            
            for item in rules_list:
                gid = item.get('group_id')
                aid = item.get('attr_id')
                
                if gid not in valid_group_ids or aid not in valid_attr_ids:
                    missing_sde_count += 1
                    continue
                    
                new_rules.append(FitAnalysisRule(
                    group_id=gid,
                    attribute_id=aid,
                    comparison_logic=item.get('logic', 'higher'),
                    tolerance_percent=item.get('tolerance', 0.0),
                    priority=item.get('priority', 0)
                ))
            
            FitAnalysisRule.objects.bulk_create(new_rules)
            created_count = len(new_rules)
            
        msg = f"Imported {created_count} rules."
        if missing_sde_count > 0:
            msg += f" (Skipped {missing_sde_count} due to missing SDE data)."
            
        return JsonResponse({'success': True, 'message': msg})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Server Error: {str(e)}"})
from django.shortcuts import render