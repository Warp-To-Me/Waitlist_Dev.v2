import json
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction

from core.permissions import can_manage_doctrines, get_template_base, get_mgmt_context
from core.eft_parser import EFTParser
from waitlist_data.models import DoctrineCategory, DoctrineFit, DoctrineTag, FitModule
from pilot_data.models import ItemType
from .helpers import _process_category_icons, _determine_slot

def doctrine_list(request):
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'fits__ship_type', 'fits__tags',
        'subcategories__fits__ship_type', 'subcategories__fits__tags',
        'subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__subcategories__fits__tags'
    )
    for cat in categories:
        _process_category_icons(cat)
    context = {
        'categories': categories,
        'base_template': get_template_base(request)
    }
    return render(request, 'doctrines/public_index.html', context)

def doctrine_detail_api(request, fit_id):
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    hull = fit.ship_type
    raw_modules = fit.modules.select_related('item_type').prefetch_related('item_type__attributes').all()
    aggregated = {}
    for mod in raw_modules:
        key = (mod.slot, mod.item_type.type_id)
        if key not in aggregated:
            aggregated[key] = {
                'name': mod.item_type.type_name, 'id': mod.item_type.type_id,
                'quantity': 0, 'slot': mod.slot
            }
        aggregated[key]['quantity'] += mod.quantity

    modules_by_slot = { 'high': [], 'mid': [], 'low': [], 'rig': [], 'subsystem': [], 'drone': [], 'cargo': [] }
    for data in aggregated.values():
        if data['slot'] in modules_by_slot:
            modules_by_slot[data['slot']].append(data)

    high_total = int(hull.high_slots)
    mid_total = int(hull.mid_slots)
    low_total = int(hull.low_slots)
    rig_total = int(hull.rig_slots)
    
    if hull.group_id == 963:
        for mod in raw_modules:
            attrs = {a.attribute_id: a.value for a in mod.item_type.attributes.all()}
            if 14 in attrs: high_total += int(attrs[14])
            if 13 in attrs: mid_total += int(attrs[13])
            if 12 in attrs: low_total += int(attrs[12])

    slot_config = [
        ('High Slots', 'high', high_total), ('Mid Slots', 'mid', mid_total),
        ('Low Slots', 'low', low_total), ('Rigs', 'rig', rig_total),
        ('Subsystems', 'subsystem', 5 if hull.group_id == 963 else 0),
        ('Drone Bay', 'drone', 0), ('Cargo Hold', 'cargo', 0),
    ]

    slot_groups = []
    for label, key, total_attr in slot_config:
        mods = modules_by_slot.get(key, [])
        used_count = sum(m['quantity'] for m in mods)
        if total_attr < used_count: total_attr = used_count
        is_hardpoint = key in ['high', 'mid', 'low', 'rig', 'subsystem']
        empties_count = max(0, total_attr - used_count) if is_hardpoint else 0
        if total_attr > 0 or used_count > 0:
            slot_groups.append({
                'name': label, 'key': key, 'total': total_attr if is_hardpoint else None,
                'used': used_count if is_hardpoint else None, 'modules': mods,
                'empties_count': empties_count, 'is_hardpoint': is_hardpoint
            })

    data = {
        'id': fit.id, 'name': fit.name, 'hull': hull.type_name,
        'hull_id': hull.type_id, 'description': fit.description,
        'eft_format': fit.eft_format, 'slots': slot_groups
    }
    return JsonResponse(data)

@login_required
@user_passes_test(can_manage_doctrines)
def manage_doctrines(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            fit_id = request.POST.get('fit_id')
            DoctrineFit.objects.filter(id=fit_id).delete()
            return redirect('manage_doctrines')
        elif action == 'create' or action == 'update':
            raw_eft = request.POST.get('eft_paste')
            cat_id = request.POST.get('category_id')
            description = request.POST.get('description', '')
            tag_ids = request.POST.getlist('tags')
            parser = EFTParser(raw_eft)
            if parser.parse():
                category = get_object_or_404(DoctrineCategory, id=cat_id)
                if action == 'update':
                    fit_id = request.POST.get('fit_id')
                    fit = get_object_or_404(DoctrineFit, id=fit_id)
                    fit.name = parser.fit_name; fit.category = category; fit.ship_type = parser.hull_obj
                    fit.eft_format = parser.raw_text; fit.description = description; fit.save()
                    fit.modules.all().delete()
                else:
                    fit = DoctrineFit.objects.create(name=parser.fit_name, category=category, ship_type=parser.hull_obj, eft_format=parser.raw_text, description=description)
                if tag_ids: fit.tags.set(tag_ids)
                else: fit.tags.clear()
                for item in parser.items:
                    slot = _determine_slot(item['obj'])
                    FitModule.objects.create(fit=fit, item_type=item['obj'], quantity=item['quantity'], slot=slot)
            return redirect('manage_doctrines')
    
    # Prefetch deeply nested subcategories to ensure the dropdown has all levels available
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'subcategories',
        'subcategories__subcategories',
        'subcategories__subcategories__subcategories'
    )
    
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'order')
    tags = DoctrineTag.objects.all()
    context = { 'categories': categories, 'fits': fits, 'tags': tags, 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/doctrines.html', context)

@login_required
@user_passes_test(can_manage_doctrines)
def api_export_doctrines(request):
    """
    Exports full doctrine configuration to a Base64 encoded JSON string.
    Includes: Tags, Categories (nested), Fits, and Modules.
    """
    export_data = {
        'tags': [],
        'categories': [],
        'fits': [],
        'timestamp': timezone.now().isoformat()
    }

    # 1. Tags
    for tag in DoctrineTag.objects.all().order_by('order'):
        export_data['tags'].append({
            'name': tag.name,
            'style': tag.style_classes,
            'order': tag.order
        })

    # 2. Categories
    # We export hierarchy via slug references
    for cat in DoctrineCategory.objects.all().order_by('order'):
        export_data['categories'].append({
            'name': cat.name,
            'slug': cat.slug,
            'parent_slug': cat.parent.slug if cat.parent else None,
            'order': cat.order,
            'target_column': cat.target_column
        })

    # 3. Fits
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags', 'modules__item_type').all().order_by('order')
    
    for fit in fits:
        modules_data = []
        for mod in fit.modules.all():
            modules_data.append({
                'type_id': mod.item_type.type_id,
                'quantity': mod.quantity,
                'slot': mod.slot
            })

        export_data['fits'].append({
            'name': fit.name,
            'category_slug': fit.category.slug,
            'ship_type_id': fit.ship_type.type_id,
            'eft_format': fit.eft_format,
            'description': fit.description,
            'is_doctrinal': fit.is_doctrinal,
            'order': fit.order,
            'tags': list(fit.tags.values_list('name', flat=True)),
            'modules': modules_data
        })

    json_str = json.dumps(export_data)
    encoded_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    
    return JsonResponse({
        'success': True, 
        'export_string': encoded_str,
        'summary': f"Exported {len(export_data['fits'])} fits, {len(export_data['categories'])} categories."
    })

@login_required
@user_passes_test(can_manage_doctrines)
@require_POST
def api_import_doctrines(request):
    """
    Imports doctrine configuration from string. 
    WIPES EXISTING DATA to ensure clean state.
    """
    try:
        data = json.loads(request.body)
        import_string = data.get('import_string', '')
        
        if not import_string:
            return JsonResponse({'success': False, 'error': 'Empty import string'})

        try:
            decoded_bytes = base64.b64decode(import_string)
            import_data = json.loads(decoded_bytes.decode('utf-8'))
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid Base64/JSON format'})

        with transaction.atomic():
            # 1. WIPE EXISTING
            FitModule.objects.all().delete()
            DoctrineFit.objects.all().delete()
            DoctrineCategory.objects.all().delete()
            DoctrineTag.objects.all().delete()

            # 2. IMPORT TAGS
            tag_map = {} # name -> obj
            for t_data in import_data.get('tags', []):
                tag = DoctrineTag.objects.create(
                    name=t_data['name'],
                    style_classes=t_data.get('style', 'bg-slate-700 text-slate-300 border-slate-600'),
                    order=t_data.get('order', 0)
                )
                tag_map[tag.name] = tag

            # 3. IMPORT CATEGORIES (Two Pass)
            cat_map = {} # slug -> obj
            
            # Pass A: Create Roots and Children (ignoring parent link)
            raw_cats = import_data.get('categories', [])
            for c_data in raw_cats:
                cat = DoctrineCategory.objects.create(
                    name=c_data['name'],
                    slug=c_data['slug'],
                    order=c_data.get('order', 0),
                    target_column=c_data.get('target_column', 'inherit')
                )
                cat_map[cat.slug] = cat

            # Pass B: Link Parents
            for c_data in raw_cats:
                parent_slug = c_data.get('parent_slug')
                if parent_slug and parent_slug in cat_map:
                    child = cat_map[c_data['slug']]
                    child.parent = cat_map[parent_slug]
                    child.save()

            # 4. IMPORT FITS
            raw_fits = import_data.get('fits', [])
            missing_items = set()
            created_fits = 0

            for f_data in raw_fits:
                # Resolve dependencies
                cat_slug = f_data.get('category_slug')
                if cat_slug not in cat_map: continue # Skip if category missing
                
                ship_type_id = f_data.get('ship_type_id')
                try:
                    ship_obj = ItemType.objects.get(type_id=ship_type_id)
                except ItemType.DoesNotExist:
                    missing_items.add(ship_type_id)
                    continue

                fit = DoctrineFit.objects.create(
                    name=f_data['name'],
                    category=cat_map[cat_slug],
                    ship_type=ship_obj,
                    eft_format=f_data.get('eft_format', ''),
                    description=f_data.get('description', ''),
                    is_doctrinal=f_data.get('is_doctrinal', True),
                    order=f_data.get('order', 0)
                )
                
                # Link Tags
                tags_to_add = []
                for t_name in f_data.get('tags', []):
                    if t_name in tag_map:
                        tags_to_add.append(tag_map[t_name])
                if tags_to_add:
                    fit.tags.set(tags_to_add)

                # Create Modules
                modules_to_create = []
                for m_data in f_data.get('modules', []):
                    mod_type_id = m_data['type_id']
                    try:
                        mod_item = ItemType.objects.get(type_id=mod_type_id)
                        modules_to_create.append(FitModule(
                            fit=fit,
                            item_type=mod_item,
                            quantity=m_data.get('quantity', 1),
                            slot=m_data.get('slot', 'cargo')
                        ))
                    except ItemType.DoesNotExist:
                        missing_items.add(mod_type_id)
                
                FitModule.objects.bulk_create(modules_to_create)
                created_fits += 1

        msg = f"Imported {created_fits} fits, {len(cat_map)} categories."
        if missing_items:
            msg += f" WARNING: {len(missing_items)} SDE items were missing (Check SDE update)."

        return JsonResponse({'success': True, 'message': msg})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})