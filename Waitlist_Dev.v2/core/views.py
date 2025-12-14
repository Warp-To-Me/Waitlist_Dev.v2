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

from django.db import models
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
            'type': f.type,
            'status': f.status,
            'join_token': f.join_token,
            'created_at': f.created_at,
            'fc_name': fc_name,
            'description': f.description,
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
        'description': cat.description,
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