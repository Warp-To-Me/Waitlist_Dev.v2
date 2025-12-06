from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.http import JsonResponse
from core.utils import get_role_priority, ROLE_HIERARCHY
from core.eft_parser import EFTParser
from .models import DoctrineCategory, DoctrineFit, FitModule, DoctrineTag
from pilot_data.models import TypeEffect, ItemGroup

# --- Helpers ---

def get_template_base(request):
    """Determines if we should render the full page or just the content block."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return 'base_content.html'
    return 'base.html'

def is_admin(user):
    if user.is_superuser: return True
    return user.groups.filter(name='Admin').exists()

def is_fleet_command(user):
    if user.is_superuser: return True
    allowed = ROLE_HIERARCHY[:8]
    return user.groups.filter(name__in=allowed).exists()

def get_mgmt_context(user):
    return {
        'can_view_fleets': is_fleet_command(user),
        'can_view_admin': is_admin(user)
    }

def _process_category_icons(category):
    """
    Recursively collects unique ship types for a category and its descendants.
    Attaches 'unique_ship_icons' list to the category object.
    """
    seen_ids = set()
    unique_ships = []

    # 1. Add Direct Fits
    for fit in category.fits.all():
        if fit.ship_type.type_id not in seen_ids:
            seen_ids.add(fit.ship_type.type_id)
            unique_ships.append(fit.ship_type)

    # 2. Add Subcategory Fits (Recursive)
    for sub in category.subcategories.all():
        # Process the subcategory first so it has its own list ready
        sub_ships = _process_category_icons(sub) 
        
        # Add sub's ships to this category's list if not seen
        for ship in sub_ships:
            if ship.type_id not in seen_ids:
                seen_ids.add(ship.type_id)
                unique_ships.append(ship)
    
    # Attach to object (transient attribute for template)
    category.unique_ship_icons = unique_ships
    return unique_ships

# --- PUBLIC VIEWS ---

def doctrine_list(request):
    """
    Public accessible page showing all fits.
    """
    # Optimized Query including TAGS at every level
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'fits__ship_type', 'fits__tags',
        'subcategories__fits__ship_type', 'subcategories__fits__tags',
        'subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__subcategories__fits__tags'
    )
    
    # Post-process to calculate unique icons for headers
    for cat in categories:
        _process_category_icons(cat)
    
    context = {
        'categories': categories,
        'base_template': get_template_base(request)
    }
    
    return render(request, 'doctrines/public_index.html', context)

def doctrine_detail_api(request, fit_id):
    """
    Returns JSON data for a specific fit to populate the modal.
    Calculates slot usage and empty slots based on SDE attributes.
    """
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    hull = fit.ship_type

    # 1. Fetch raw modules
    # PREFETCH ATTRIBUTES: Essential for T3C calculation without N+1 queries
    raw_modules = fit.modules.select_related('item_type').prefetch_related('item_type__attributes').all()

    # 2. Group by slot
    modules_by_slot = {
        'high': [], 'mid': [], 'low': [], 'rig': [], 
        'subsystem': [], 'drone': [], 'cargo': []
    }

    for mod in raw_modules:
        if mod.slot in modules_by_slot:
            is_hardpoint = mod.slot in ['high', 'mid', 'low', 'rig', 'subsystem']
            
            item_data = {
                'name': mod.item_type.type_name,
                'id': mod.item_type.type_id,
                'quantity': mod.quantity
            }

            if is_hardpoint:
                # Expand hardpoints
                for _ in range(mod.quantity):
                    entry = item_data.copy()
                    entry['quantity'] = 1
                    modules_by_slot[mod.slot].append(entry)
            else:
                # Keep grouped (Cargo/Drones)
                modules_by_slot[mod.slot].append(item_data)

    # 3. Calculate Totals (Including T3C Logic)
    
    # Base Hull Slots
    high_total = int(hull.high_slots)
    mid_total = int(hull.mid_slots)
    low_total = int(hull.low_slots)
    rig_total = int(hull.rig_slots)
    
    # T3C Logic: Strategic Cruisers (Group 963)
    if hull.group_id == 963:
        # Iterate over modules to find subsystems and sum their slot modifiers
        for mod in raw_modules:
            # We convert the prefetched attributes list to a dict for fast lookup in memory
            # attrs = { 14: 1.0, 13: 2.0 ... }
            attrs = {a.attribute_id: a.value for a in mod.item_type.attributes.all()}
            
            # Attribute IDs for Slot Modifiers:
            # 14 = highSlots
            # 13 = medSlots
            # 12 = lowSlots
            
            if 14 in attrs:
                high_total += int(attrs[14])
            if 13 in attrs:
                mid_total += int(attrs[13])
            if 12 in attrs:
                low_total += int(attrs[12])

    # Configuration List
    slot_config = [
        ('High Slots', 'high', high_total),
        ('Mid Slots', 'mid', mid_total),
        ('Low Slots', 'low', low_total),
        ('Rigs', 'rig', rig_total),
        ('Subsystems', 'subsystem', 5 if 'Strategic Cruiser' in str(hull.group_id) or hull.group_id == 963 else 0),
        ('Drone Bay', 'drone', 0),
        ('Cargo Hold', 'cargo', 0),
    ]

    slot_groups = []

    for label, key, total_attr in slot_config:
        mods = modules_by_slot.get(key, [])
        used_count = len(mods)
        
        # Heuristic: If attribute says 0 but we have modules (e.g. missing SDE data), expand to match used.
        if total_attr < used_count:
            total_attr = used_count

        # Only hardpoints show "Empty Slot" placeholders
        is_hardpoint = key in ['high', 'mid', 'low', 'rig', 'subsystem']
        empties_count = 0
        
        if is_hardpoint:
            empties_count = max(0, total_attr - used_count)
        
        if total_attr > 0 or used_count > 0:
            slot_groups.append({
                'name': label,
                'key': key,
                'total': total_attr if is_hardpoint else None,
                'used': used_count if is_hardpoint else None,
                'modules': mods,
                'empties_count': empties_count,
                'is_hardpoint': is_hardpoint
            })

    data = {
        'id': fit.id,
        'name': fit.name,
        'hull': hull.type_name,
        'hull_id': hull.type_id,
        'description': fit.description,
        'eft_block': fit.eft_format,
        'slots': slot_groups
    }
    return JsonResponse(data)


# --- MANAGEMENT VIEWS ---

@login_required
@user_passes_test(is_admin)
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
                    fit.name = parser.fit_name
                    fit.category = category
                    fit.ship_type = parser.hull_obj
                    fit.eft_format = parser.raw_text
                    fit.description = description
                    fit.save()
                    
                    # Clear old modules to re-add them
                    fit.modules.all().delete()
                else:
                    # Create New
                    fit = DoctrineFit.objects.create(
                        name=parser.fit_name,
                        category=category,
                        ship_type=parser.hull_obj,
                        eft_format=parser.raw_text,
                        description=description
                    )
                
                # Set Tags (Works for both create and update)
                if tag_ids:
                    fit.tags.set(tag_ids)
                else:
                    fit.tags.clear()
                
                # Re-create Modules
                for item in parser.items:
                    FitModule.objects.create(
                        fit=fit,
                        item_type=item['obj'],
                        quantity=item['quantity'],
                        # Use new robust slot detector
                        slot=_determine_slot(item['obj'])
                    )
            else:
                print(f"Parser Error: {parser.error}")
                # Ideally flash a message here

            return redirect('manage_doctrines')

    categories = DoctrineCategory.objects.all()
    # Fits ordered by order then name
    fits = DoctrineFit.objects.select_related('category', 'ship_type').prefetch_related('tags').order_by('category__name', 'order')
    tags = DoctrineTag.objects.all()

    context = {
        'categories': categories,
        'fits': fits,
        'tags': tags,
        'base_template': get_template_base(request)
    }
    
    context.update(get_mgmt_context(request.user))
    
    return render(request, 'management/doctrines.html', context)

def _determine_slot(item_type):
    """
    Determines the slot type (high/mid/low/rig/subsystem) for an item using 
    EVE Dogma Effects or Category fallback.
    """
    # 1. Effect ID check (Most accurate for modules)
    # 12 = hiPower (High Slot)
    # 13 = medPower (Mid Slot)
    # 11 = loPower (Low Slot)
    # 2663 = rigSlot (Rig Slot)
    # 3772 = subSystem (Subsystem)
    
    effects = set(TypeEffect.objects.filter(item=item_type).values_list('effect_id', flat=True))
    
    if 12 in effects: return 'high'
    if 13 in effects: return 'mid'
    if 11 in effects: return 'low'
    if 2663 in effects: return 'rig'
    
    # 2. Category Fallback
    # Some items (like Drones, Ammo, or Subsystems if effect is missing) are better identified by category.
    # Group -> Category lookup
    try:
        group = ItemGroup.objects.get(group_id=item_type.group_id)
        
        # Category 32 = Subsystems
        if group.category_id == 32: return 'subsystem'
        
        # Category 18 = Drones
        if group.category_id == 18: return 'drone'
        
        # Category 87 = Fighters (Treat as drone/fighter bay)
        if group.category_id == 87: return 'drone'

        # Category 8 = Charge (Ammo) -> Default to Cargo
        if group.category_id == 8: return 'cargo'
        
    except ItemGroup.DoesNotExist:
        pass

    # Default fallback
    return 'cargo'