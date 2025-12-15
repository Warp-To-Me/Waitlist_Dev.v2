import json
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Count, Subquery
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Core
from core.permissions import get_template_base, can_manage_doctrines, get_mgmt_context

# Models
from pilot_data.models import EveCharacter, ItemType, ItemGroup
from waitlist_data.models import Fleet, DoctrineCategory, DoctrineFit, FitModule, DoctrineTag
from core.models import Ban
from core.eft_parser import EFTParser

from django.db import models, transaction
from django.utils import timezone

@api_view(['GET'])
def banned_view(request):
    active_ban = Ban.objects.filter(
        user=request.user
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
    ).order_by('-created_at').first()

    if not active_ban:
        return Response({'is_banned': False})

    return Response({
        'is_banned': True,
        'reason': active_ban.reason,
        'expires_at': active_ban.expires_at,
        'created_at': active_ban.created_at,
        'admin_name': active_ban.admin.username if active_ban.admin else 'System'
    })

@api_view(['GET'])
def landing_page(request):
    active_fleets_qs = Fleet.objects.filter(is_active=True).select_related('commander').order_by('-created_at')
    
    fleets_list = []
    # Fetch commander details efficiently
    commander_ids = [f.commander_id for f in active_fleets_qs]
    mains = EveCharacter.objects.filter(user_id__in=commander_ids, is_main=True).values('user_id', 'character_name')
    fc_name_map = {m['user_id']: m['character_name'] for m in mains}
    
    # Fill gaps with any character if main not found (edge case)
    missing = set(commander_ids) - set(fc_name_map.keys())
    if missing:
        others = EveCharacter.objects.filter(user_id__in=missing).values('user_id', 'character_name')
        for o in others:
            if o['user_id'] not in fc_name_map: fc_name_map[o['user_id']] = o['character_name']

    for f in active_fleets_qs:
        fc_name = fc_name_map.get(f.commander_id, f.commander.username)
        fleets_list.append({
            'id': f.id,
            # Removed non-existent fields 'type' and 'status'
            'join_token': f.join_token,
            'created_at': f.created_at,
            'fc_name': fc_name,
            #'description': f.motd, # Mapped description to motd
            'is_active': f.is_active
        })

    # Redirect logic is now client-side responsibility, but we can hint it
    should_redirect = False
    redirect_token = None
    if request.user.is_authenticated and len(fleets_list) == 1:
        should_redirect = True
        redirect_token = fleets_list[0]['join_token']

    return Response({
        'fleets': fleets_list,
        'should_redirect': should_redirect,
        'redirect_token': redirect_token
    })

@api_view(['GET'])
def access_denied(request):
    return Response({'error': 'Access Denied', 'code': 403}, status=403)

# --- DOCTRINES (Legacy/Shared) ---

# Helper to serialize nested categories
def serialize_category(cat):
    data = {
        'id': cat.id,
        'name': cat.name,
        # Removed 'description': cat.description (Field does not exist on DoctrineCategory)
        'fits': [],
        'subcategories': []
    }
    for fit in cat.fits.all():
        data['fits'].append({
            'id': fit.id,
            'name': fit.name,
            'hull': fit.ship_type.type_name,
            'hull_id': fit.ship_type.type_id,
            'tags': [t.name for t in fit.tags.all()]
        })
    for sub in cat.subcategories.all():
        data['subcategories'].append(serialize_category(sub))
    return data

@api_view(['GET'])
def doctrine_list(request):
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'fits__ship_type', 'fits__tags', 'subcategories__fits__ship_type', 'subcategories__fits__tags',
        'subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__subcategories__fits__tags'
    )
    
    result = [serialize_category(c) for c in categories]
    return Response(result)

@api_view(['GET'])
def doctrine_detail_api(request, fit_id):
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    modules = []
    for mod in fit.modules.select_related('item_type').all():
        modules.append({ 'name': mod.item_type.type_name, 'quantity': mod.quantity, 'icon_id': mod.item_type.type_id })
    data = {
        'id': fit.id, 'name': fit.name, 'hull': fit.ship_type.type_name,
        'hull_id': fit.ship_type.type_id, 'description': fit.description,
        'eft_block': fit.eft_format, 'modules': modules
    }
    return Response(data)

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated]) # Further checked by manual check or logic
def manage_doctrines(request):
    # Check permission
    if not can_manage_doctrines(request.user):
         return Response({'error': 'Permission denied'}, status=403)

    if request.method == 'POST':
        action = request.data.get('action')
        
        if action == 'delete':
            fit_id = request.data.get('fit_id')
            DoctrineFit.objects.filter(id=fit_id).delete()
            return Response({'status': 'deleted'})
            
        elif action == 'create' or action == 'update':
            raw_eft = request.data.get('eft_paste')
            cat_id = request.data.get('category_id')
            description = request.data.get('description', '')
            tag_ids = request.data.get('tags', []) # Expect list of IDs
            
            parser = EFTParser(raw_eft)
            if parser.parse():
                category = get_object_or_404(DoctrineCategory, id=cat_id)
                if action == 'update':
                    fit_id = request.data.get('fit_id')
                    fit = get_object_or_404(DoctrineFit, id=fit_id)
                    fit.name = parser.fit_name; fit.category = category; fit.ship_type = parser.hull_obj
                    fit.eft_format = parser.raw_text; fit.description = description; fit.save()
                    fit.modules.all().delete()
                else:
                    fit = DoctrineFit.objects.create(name=parser.fit_name, category=category, ship_type=parser.hull_obj, eft_format=parser.raw_text, description=description)
                
                if tag_ids: fit.tags.set(tag_ids)
                else: fit.tags.clear()
                
                for item in parser.items:
                    FitModule.objects.create(fit=fit, item_type=item['obj'], quantity=item['quantity'])
                
                return Response({'status': 'saved', 'fit_id': fit.id})
            else:
                return Response({'error': 'Failed to parse EFT'}, status=400)

    # GET: List everything needed for the management UI
    categories = DoctrineCategory.objects.all().values('id', 'name', 'parent_id')
    
    # Flat list of fits with category info for the table
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'order')
    fits_data = []
    for f in fits:
        fits_data.append({
            'id': f.id,
            'name': f.name,
            'category_name': f.category.name,
            'hull': f.ship_type.type_name,
            'tags': [{'id': t.id, 'name': t.name} for t in f.tags.all()],
            'updated_at': f.updated_at
        })

    tags = DoctrineTag.objects.all().values('id', 'name')
    
    return Response({
        'categories': list(categories),
        'fits': fits_data,
        'tags': list(tags)
    })

# --- NEW REACT MANAGEMENT ENDPOINTS ---

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_doctrine_data(request):
    if not can_manage_doctrines(request.user):
        return Response({'error': 'Permission Denied'}, status=403)

    # Fetch recursive categories logic manually or just basic list for dropdown
    # The frontend expects 'categories' (flat or nested?).
    # Based on frontend code `renderCategoryOptions`, it handles nested via 'subcategories' key.

    # Let's rebuild the nested structure for the dropdown
    all_cats = DoctrineCategory.objects.all().order_by('name')
    cat_map = {c.id: {'id': c.id, 'name': c.name, 'subcategories': [], 'parent_id': c.parent_id} for c in all_cats}
    nested_cats = []

    for c in all_cats:
        if c.parent_id:
            if c.parent_id in cat_map:
                cat_map[c.parent_id]['subcategories'].append(cat_map[c.id])
        else:
            nested_cats.append(cat_map[c.id])

    # Fits
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'name')
    fits_data = []
    for f in fits:
        # Build path string
        path = f.category.name
        parent = f.category.parent
        while parent:
            path = f"{parent.name} > {path}"
            parent = parent.parent

        fits_data.append({
            'id': f.id,
            'name': f.name,
            'ship_name': f.ship_type.type_name,
            'category_id': f.category.id,
            'category_path': path,
            'description': f.description,
            'eft_format': f.eft_format,
            'tags': [t.name for t in f.tags.all()],
            'tag_ids': [t.id for t in f.tags.all()]
        })

    tags = DoctrineTag.objects.all().values('id', 'name')

    return Response({
        'categories': nested_cats,
        'fits': fits_data,
        'tags': list(tags)
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_doctrine_save(request):
    if not can_manage_doctrines(request.user):
        return Response({'success': False, 'error': 'Permission Denied'}, status=403)

    action = request.data.get('action')

    try:
        if action == 'delete':
            fit_id = request.data.get('fit_id')
            DoctrineFit.objects.filter(id=fit_id).delete()
            return Response({'success': True})

        elif action in ['create', 'update']:
            raw_eft = request.data.get('eft_paste')
            cat_id = request.data.get('category_id')
            description = request.data.get('description', '')
            tag_ids = request.data.get('tags', [])

            parser = EFTParser(raw_eft)
            if not parser.parse():
                return Response({'success': False, 'error': 'Failed to parse EFT block.'}, status=400)

            category = get_object_or_404(DoctrineCategory, id=cat_id)

            with transaction.atomic():
                if action == 'update':
                    fit = get_object_or_404(DoctrineFit, id=request.data.get('fit_id'))
                    fit.name = parser.fit_name
                    fit.category = category
                    fit.ship_type = parser.hull_obj
                    fit.eft_format = parser.raw_text
                    fit.description = description
                    fit.save()
                    fit.modules.all().delete()
                else:
                    fit = DoctrineFit.objects.create(
                        name=parser.fit_name,
                        category=category,
                        ship_type=parser.hull_obj,
                        eft_format=parser.raw_text,
                        description=description
                    )

                if tag_ids:
                    fit.tags.set(tag_ids)
                else:
                    fit.tags.clear()

                modules_to_create = []
                for item in parser.items:
                    modules_to_create.append(FitModule(
                        fit=fit,
                        item_type=item['obj'],
                        quantity=item['quantity']
                    ))
                FitModule.objects.bulk_create(modules_to_create)

            return Response({'success': True, 'fit_id': fit.id})

    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_doctrine_export(request):
    if not can_manage_doctrines(request.user): return Response({'success': False, 'error': 'Permission Denied'}, status=403)

    # Export categories and fits
    # Structure: { 'categories': [...], 'fits': [...] }
    # Tags are probably safe to recreate by name if missing

    cats = list(DoctrineCategory.objects.all().values('id', 'name', 'parent_id', 'slug', 'target_column'))
    fits = DoctrineFit.objects.all().select_related('ship_type', 'category').prefetch_related('tags')

    fits_export = []
    for f in fits:
        fits_export.append({
            'name': f.name,
            'hull': f.ship_type.type_name,
            'category_slug': f.category.slug,
            'eft': f.eft_format,
            'description': f.description,
            'tags': [t.name for t in f.tags.all()]
        })

    data_obj = {'categories': cats, 'fits': fits_export}
    json_str = json.dumps(data_obj)
    b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    return Response({'success': True, 'export_string': b64_str})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_doctrine_import(request):
    if not can_manage_doctrines(request.user): return Response({'success': False, 'error': 'Permission Denied'}, status=403)

    import_string = request.data.get('import_string', '')
    try:
        json_bytes = base64.b64decode(import_string)
        data = json.loads(json_bytes.decode('utf-8'))
    except:
        return Response({'success': False, 'error': 'Invalid Import String'}, status=400)

    # Process
    try:
        with transaction.atomic():
            # WIPE EXISTING
            DoctrineFit.objects.all().delete()
            DoctrineCategory.objects.all().delete()

            # Recreate Categories
            # Need to handle hierarchy (parents first). Simple approach: Multi-pass or sort by ID if preserved?
            # IDs might not match new DB. Use slugs/names.

            # 1. Create all categories flat first
            slug_map = {}
            pending_parents = []

            for c in data.get('categories', []):
                cat = DoctrineCategory.objects.create(
                    name=c['name'],
                    slug=c['slug'],
                    target_column=c.get('target_column', 'inherit')
                )
                slug_map[c['id']] = cat # Map OLD id to NEW obj
                if c['parent_id']:
                    pending_parents.append((cat, c['parent_id']))

            # 2. Link parents
            for cat, old_parent_id in pending_parents:
                if old_parent_id in slug_map:
                    cat.parent = slug_map[old_parent_id]
                    cat.save()

            # 3. Create Fits
            for f in data.get('fits', []):
                hull = ItemType.objects.filter(type_name=f['hull']).first()
                if not hull: continue # Skip if hull invalid

                # Find category by slug (re-mapped)
                # We need to find the new category object that corresponds to the old slug
                # But the export stored slug.
                cat = DoctrineCategory.objects.filter(slug=f['category_slug']).first()
                if not cat: continue # Skip if cat missing

                parser = EFTParser(f['eft'])
                if parser.parse():
                    fit = DoctrineFit.objects.create(
                        name=f['name'],
                        category=cat,
                        ship_type=hull,
                        eft_format=f['eft'],
                        description=f['description']
                    )

                    # Tags
                    for t_name in f.get('tags', []):
                        tag, _ = DoctrineTag.objects.get_or_create(name=t_name)
                        fit.tags.add(tag)

                    # Modules
                    modules = []
                    for item in parser.items:
                        modules.append(FitModule(
                            fit=fit,
                            item_type=item['obj'],
                            quantity=item['quantity']
                        ))
                    FitModule.objects.bulk_create(modules)

        return Response({'success': True, 'message': 'Import successful.'})
    except Exception as e:
        return Response({'success': False, 'error': f"Import failed: {str(e)}"}, status=500)
