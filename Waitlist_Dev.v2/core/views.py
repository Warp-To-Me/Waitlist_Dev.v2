from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Count, Subquery

# Core
from core.permissions import get_template_base, can_manage_doctrines, get_mgmt_context

# Models
from pilot_data.models import EveCharacter, ItemType, ItemGroup
from waitlist_data.models import Fleet, DoctrineCategory, DoctrineFit, FitModule, DoctrineTag
from core.models import Ban
from core.eft_parser import EFTParser

from django.db import models
from django.utils import timezone

@login_required
def banned_view(request):
    active_ban = Ban.objects.filter(
        user=request.user
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
    ).order_by('-created_at').first()

    if not active_ban:
        return redirect('landing_page')

    context = {
        'ban': active_ban,
        'base_template': get_template_base(request)
    }
    return render(request, 'banned.html', context)

def landing_page(request):
    active_fleets_qs = Fleet.objects.filter(is_active=True).select_related('commander').order_by('-created_at')
    if request.user.is_authenticated and active_fleets_qs.count() == 1:
        return redirect('fleet_dashboard', token=active_fleets_qs.first().join_token)
    fleets_list = list(active_fleets_qs)
    if fleets_list:
        commander_user_ids = [f.commander_id for f in fleets_list]
        mains = EveCharacter.objects.filter(user_id__in=commander_user_ids, is_main=True).values('user_id', 'character_name')
        fc_name_map = {m['user_id']: m['character_name'] for m in mains}
        missing_ids = set(commander_user_ids) - set(fc_name_map.keys())
        if missing_ids:
            others = EveCharacter.objects.filter(user_id__in=missing_ids).values('user_id', 'character_name')
            for o in others:
                if o['user_id'] not in fc_name_map: fc_name_map[o['user_id']] = o['character_name']
        for fleet in fleets_list:
            fleet.fc_name = fc_name_map.get(fleet.commander_id, fleet.commander.username)
    context = { 'active_fleets': fleets_list, 'base_template': get_template_base(request) }
    return render(request, 'landing.html', context)

def access_denied(request):
    context = { 'base_template': get_template_base(request) }
    return render(request, 'access_denied.html', context)

# --- DOCTRINES (Legacy/Shared) ---

def doctrine_list(request):
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'fits__ship_type', 'fits__tags', 'subcategories__fits__ship_type', 'subcategories__fits__tags',
        'subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__subcategories__fits__tags'
    )
    context = { 'categories': categories, 'base_template': get_template_base(request) }
    return render(request, 'doctrines/public_index.html', context)

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
                    FitModule.objects.create(fit=fit, item_type=item['obj'], quantity=item['quantity'])
            return redirect('manage_doctrines')
    categories = DoctrineCategory.objects.all()
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'order')
    tags = DoctrineTag.objects.all()
    context = { 'categories': categories, 'fits': fits, 'tags': tags, 'base_template': get_template_base(request) }
    context.update(get_mgmt_context(request.user))
    return render(request, 'management/doctrines.html', context)