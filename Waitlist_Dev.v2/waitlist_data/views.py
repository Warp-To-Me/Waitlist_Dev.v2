from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import requests # For manual ESI calls if needed

# Core Imports
from core.utils import get_role_priority, ROLE_HIERARCHY
from core.eft_parser import EFTParser

# Model Imports
from pilot_data.models import EveCharacter, TypeEffect, ItemGroup
from .models import DoctrineCategory, DoctrineFit, FitModule, DoctrineTag, Fleet, WaitlistEntry

# ESI Services
from esi_calls.fleet_service import get_fleet_members, invite_to_fleet, get_auth_header, ESI_BASE

# --- HELPERS ---

def get_template_base(request):
    """Determines if we should render the full page or just the content block for SPA."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return 'base_content.html'
    return 'base.html'

def is_fleet_command(user):
    """Checks if user has FC roles."""
    if user.is_superuser: return True
    allowed = ROLE_HIERARCHY[:8] # Admin down to Assault FC
    return user.groups.filter(name__in=allowed).exists()

def is_admin(user):
    if user.is_superuser: return True
    return user.groups.filter(name='Admin').exists()

def get_mgmt_context(user):
    """Standard context for management templates."""
    return {
        'can_view_fleets': is_fleet_command(user),
        'can_view_admin': is_admin(user),
        'is_fc': is_fleet_command(user)
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
        sub_ships = _process_category_icons(sub) 
        for ship in sub_ships:
            if ship.type_id not in seen_ids:
                seen_ids.add(ship.type_id)
                unique_ships.append(ship)
    
    category.unique_ship_icons = unique_ships
    return unique_ships

def _determine_slot(item_type):
    """
    Determines the slot type (high/mid/low/rig/subsystem) for an item using 
    EVE Dogma Effects or Category fallback.
    """
    effects = set(TypeEffect.objects.filter(item=item_type).values_list('effect_id', flat=True))
    
    if 12 in effects: return 'high'
    if 13 in effects: return 'mid'
    if 11 in effects: return 'low'
    if 2663 in effects: return 'rig'
    
    try:
        group = ItemGroup.objects.get(group_id=item_type.group_id)
        if group.category_id == 32: return 'subsystem'
        if group.category_id == 18: return 'drone'
        if group.category_id == 87: return 'drone'
        if group.category_id == 8: return 'cargo'
    except ItemGroup.DoesNotExist:
        pass

    return 'cargo'

# --- WEBSOCKET BROADCASTER ---

def broadcast_update(fleet_id, action, entry, target_col=None):
    """
    Sends a real-time update to the fleet's WebSocket channel.
    """
    channel_layer = get_channel_layer()
    group_name = f'fleet_{fleet_id}'
    
    payload = {
        'type': 'fleet_update',
        'action': action,
        'entry_id': entry.id
    }

    # If adding or moving, we need to send the new HTML for the card
    if action in ['add', 'move']:
        # We render the card with FC context so buttons are generated.
        # Frontend CSS/JS handles hiding them if the user isn't an FC.
        context = {'entry': entry, 'is_fc': True}
        html = render_to_string('waitlist/entry_card.html', context)
        payload['html'] = html
        payload['target_col'] = target_col

    async_to_sync(channel_layer.group_send)(group_name, payload)


# --- PUBLIC DOCTRINE VIEWS ---

def doctrine_list(request):
    """
    Public accessible page showing all fits.
    """
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related(
        'fits__ship_type', 'fits__tags',
        'subcategories__fits__ship_type', 'subcategories__fits__tags',
        'subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__fits__tags',
        'subcategories__subcategories__subcategories__fits__ship_type', 'subcategories__subcategories__subcategories__fits__tags'
    )
    
    for cat in categories:
        _process_category_icons(cat)
    
    context = {
        'categories': categories,
        'base_template': get_template_base(request)
    }
    
    return render(request, 'doctrines/public_index.html', context)

def doctrine_detail_api(request, fit_id):
    """
    Returns JSON data for a specific fit (used in modals).
    """
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    hull = fit.ship_type

    # 1. Fetch raw modules with attributes for T3C calc
    raw_modules = fit.modules.select_related('item_type').prefetch_related('item_type__attributes').all()

    # 2. Group by slot
    modules_by_slot = { 'high': [], 'mid': [], 'low': [], 'rig': [], 'subsystem': [], 'drone': [], 'cargo': [] }

    for mod in raw_modules:
        if mod.slot in modules_by_slot:
            is_hardpoint = mod.slot in ['high', 'mid', 'low', 'rig', 'subsystem']
            item_data = {
                'name': mod.item_type.type_name,
                'id': mod.item_type.type_id,
                'quantity': mod.quantity
            }

            if is_hardpoint:
                for _ in range(mod.quantity):
                    entry = item_data.copy()
                    entry['quantity'] = 1
                    modules_by_slot[mod.slot].append(entry)
            else:
                modules_by_slot[mod.slot].append(item_data)

    # 3. Calculate Totals
    high_total = int(hull.high_slots)
    mid_total = int(hull.mid_slots)
    low_total = int(hull.low_slots)
    rig_total = int(hull.rig_slots)
    
    # T3C Logic (Strategic Cruisers Group 963)
    if hull.group_id == 963:
        for mod in raw_modules:
            attrs = {a.attribute_id: a.value for a in mod.item_type.attributes.all()}
            if 14 in attrs: high_total += int(attrs[14])
            if 13 in attrs: mid_total += int(attrs[13])
            if 12 in attrs: low_total += int(attrs[12])

    slot_config = [
        ('High Slots', 'high', high_total),
        ('Mid Slots', 'mid', mid_total),
        ('Low Slots', 'low', low_total),
        ('Rigs', 'rig', rig_total),
        ('Subsystems', 'subsystem', 5 if hull.group_id == 963 else 0),
        ('Drone Bay', 'drone', 0),
        ('Cargo Hold', 'cargo', 0),
    ]

    slot_groups = []

    for label, key, total_attr in slot_config:
        mods = modules_by_slot.get(key, [])
        used_count = len(mods)
        if total_attr < used_count: total_attr = used_count
        
        is_hardpoint = key in ['high', 'mid', 'low', 'rig', 'subsystem']
        empties_count = max(0, total_attr - used_count) if is_hardpoint else 0
        
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


# --- FLEET / WAITLIST VIEWS ---

@login_required
def fleet_dashboard(request, fleet_id):
    """
    The Main Waitlist Board.
    Visible to everyone, but FCs get extra controls via context flags.
    """
    fleet = get_object_or_404(Fleet, id=fleet_id)
    
    # 1. Get active entries (Exclude rejected/left)
    entries = WaitlistEntry.objects.filter(fleet=fleet).exclude(status__in=['rejected', 'left']).select_related(
        'character', 'fit', 'fit__ship_type', 'fit__category'
    ).order_by('created_at')

    # 2. Bucket Entries into Columns
    columns = {
        'pending': [],
        'logi': [],
        'dps': [],
        'sniper': [],
        'other': []
    }
    
    for entry in entries:
        if entry.status == 'pending':
            columns['pending'].append(entry)
        else:
            # Sort approved entries by Fit Tags
            tags = [t.name.lower() for t in entry.fit.tags.all()]
            cat_name = entry.fit.category.name.lower()
            
            if 'logi' in tags or 'logistics' in cat_name:
                columns['logi'].append(entry)
            elif 'sniper' in tags:
                columns['sniper'].append(entry)
            elif 'dps' in tags or 'brawl' in tags:
                columns['dps'].append(entry)
            else:
                columns['other'].append(entry)

    # 3. Context Data
    user_chars = request.user.characters.all()
    # Needed for the X-Up Modal Dropdown
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related('subcategories__fits')

    context = {
        'fleet': fleet,
        'columns': columns,
        'user_chars': user_chars,
        'categories': categories,
        'is_fc': is_fleet_command(request.user),
        'is_commander': request.user == fleet.commander,
        'base_template': get_template_base(request)
    }
    
    return render(request, 'waitlist/dashboard.html', context)


@login_required
@require_POST
def x_up_submit(request, fleet_id):
    """
    Handles pilot submitting a fit to the waitlist via AJAX.
    """
    fleet = get_object_or_404(Fleet, id=fleet_id, is_active=True)
    char_id = request.POST.get('character_id')
    fit_id = request.POST.get('fit_id')
    
    # Verify ownership
    character = get_object_or_404(EveCharacter, character_id=char_id, user=request.user)
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    
    # Create Entry
    entry = WaitlistEntry.objects.create(
        fleet=fleet,
        character=character,
        fit=fit,
        status='pending'
    )
    
    # Broadcast to Websocket
    broadcast_update(fleet.id, 'add', entry, target_col='pending')
    
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_fleet_command)
def fleet_overview_api(request, fleet_id):
    """
    Returns JSON of current fleet members from ESI.
    """
    fleet = get_object_or_404(Fleet, id=fleet_id)
    
    # We need the FC's character to make the ESI call
    fc_char = fleet.commander.characters.filter(is_main=True).first()
    if not fc_char:
        fc_char = fleet.commander.characters.first()
        
    if not fc_char:
        return JsonResponse({'error': 'FC has no linked characters'}, status=400)
        
    # Auto-detect fleet ID if missing
    actual_fleet_id = fleet.esi_fleet_id
    if not actual_fleet_id:
        headers = get_auth_header(fc_char)
        if headers:
            resp = requests.get(f"{ESI_BASE}/characters/{fc_char.character_id}/fleet/", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                actual_fleet_id = data['fleet_id']
                fleet.esi_fleet_id = actual_fleet_id
                fleet.save()
    
    if not actual_fleet_id:
        return JsonResponse({'error': 'Could not detect active ESI Fleet'}, status=404)

    members = get_fleet_members(actual_fleet_id, fc_char)
    
    if members is None:
        return JsonResponse({'error': 'Failed to fetch members from ESI'}, status=500)
        
    # Summarize and Resolve Names
    summary = {}
    for m in members:
        ship = m['ship_name']
        summary[ship] = summary.get(ship, 0) + 1
        
        try:
            local_char = EveCharacter.objects.get(character_id=m['character_id'])
            m['name'] = local_char.character_name
        except EveCharacter.DoesNotExist:
            m['name'] = f"Guest ({m['character_id']})" 

    return JsonResponse({
        'fleet_id': actual_fleet_id,
        'member_count': len(members),
        'summary': summary,
        'members': members
    })


# --- FC MANAGEMENT ACTIONS ---

@login_required
def fc_action(request, entry_id, action):
    """
    FC Controls: Approve, Deny, Invite.
    """
    # Permission Check
    if not is_fleet_command(request.user):
        return HttpResponse("Unauthorized", status=403)

    entry = get_object_or_404(WaitlistEntry, id=entry_id)
    fleet = entry.fleet
    
    if action == 'approve':
        entry.status = 'approved'
        entry.approved_at = timezone.now()
        entry.save()
        
        # Determine Target Column based on Tags
        tags = [t.name.lower() for t in entry.fit.tags.all()]
        cat_name = entry.fit.category.name.lower()
        col = 'other'
        if 'logi' in tags or 'logistics' in cat_name: col = 'logi'
        elif 'sniper' in tags: col = 'sniper'
        elif 'dps' in tags or 'brawl' in tags: col = 'dps'
        
        # Broadcast Move
        broadcast_update(fleet.id, 'move', entry, target_col=col)
        
    elif action == 'deny':
        entry.status = 'rejected'
        entry.save()
        # Broadcast Remove
        broadcast_update(fleet.id, 'remove', entry)
        
    elif action == 'invite':
        # ESI Invite Logic
        fc_char = fleet.commander.characters.filter(is_main=True).first() or fleet.commander.characters.first()
        
        if not fleet.esi_fleet_id:
             return JsonResponse({'success': False, 'error': 'No ESI Fleet linked. Is the FC in a fleet?'})

        success = invite_to_fleet(fleet.esi_fleet_id, fc_char, entry.character.character_id)
        
        if success:
            entry.status = 'invited'
            entry.invited_at = timezone.now()
            entry.save()
            
            # Recalculate column
            tags = [t.name.lower() for t in entry.fit.tags.all()]
            cat_name = entry.fit.category.name.lower()
            col = 'other'
            if 'logi' in tags or 'logistics' in cat_name: col = 'logi'
            elif 'sniper' in tags: col = 'sniper'
            elif 'dps' in tags or 'brawl' in tags: col = 'dps'

            broadcast_update(fleet.id, 'move', entry, target_col=col)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'ESI Invite Failed'})
        
    return JsonResponse({'success': True})

@login_required
@user_passes_test(is_fleet_command)
def take_fleet_command(request, fleet_id):
    """
    Allows an FC to take over an existing fleet session.
    """
    fleet = get_object_or_404(Fleet, id=fleet_id)
    fleet.commander = request.user
    fleet.save()
    return redirect('fleet_dashboard', fleet_id=fleet.id)


# --- DOCTRINE MANAGEMENT (Admin) ---

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
                
                # Re-create Modules using the smart slot detector
                for item in parser.items:
                    FitModule.objects.create(
                        fit=fit,
                        item_type=item['obj'],
                        quantity=item['quantity'],
                        slot=_determine_slot(item['obj'])
                    )
            else:
                print(f"Parser Error: {parser.error}")

            return redirect('manage_doctrines')

    categories = DoctrineCategory.objects.all()
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