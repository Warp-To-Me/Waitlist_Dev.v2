from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.http import JsonResponse
from core.utils import get_role_priority, ROLE_HIERARCHY
from core.eft_parser import EFTParser
from .models import DoctrineCategory, DoctrineFit, FitModule

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

# --- PUBLIC VIEWS ---

def doctrine_list(request):
    """
    Public accessible page showing all fits.
    """
    categories = DoctrineCategory.objects.filter(parent__isnull=True).prefetch_related('subcategories__fits__ship_type')
    
    context = {
        'categories': categories,
    }
    
    # SPA Support: Return partial content only
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
         return render(request, 'doctrines/public_content.html', context)
         
    return render(request, 'doctrines/public_index.html', context)

def doctrine_detail_api(request, fit_id):
    """
    Returns JSON data for a specific fit to populate the modal.
    """
    fit = get_object_or_404(DoctrineFit, id=fit_id)
    
    # Serialize modules
    modules = []
    for mod in fit.modules.select_related('item_type').all():
        modules.append({
            'name': mod.item_type.type_name,
            'quantity': mod.quantity,
            'icon_id': mod.item_type.type_id
        })
        
    data = {
        'id': fit.id,
        'name': fit.name,
        'hull': fit.ship_type.type_name,
        'hull_id': fit.ship_type.type_id,
        'description': fit.description,
        'eft_block': fit.eft_format,
        'modules': modules
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

        elif action == 'create':
            raw_eft = request.POST.get('eft_paste')
            cat_id = request.POST.get('category_id')
            description = request.POST.get('description', '')
            
            parser = EFTParser(raw_eft)
            if parser.parse():
                category = get_object_or_404(DoctrineCategory, id=cat_id)
                
                # Create Fit
                fit = DoctrineFit.objects.create(
                    name=parser.fit_name,
                    category=category,
                    ship_type=parser.hull_obj,
                    eft_format=parser.raw_text,
                    description=description
                )
                
                # Create Modules
                for item in parser.items:
                    FitModule.objects.create(
                        fit=fit,
                        item_type=item['obj'],
                        quantity=item['quantity']
                    )
            else:
                # In a real app, you'd pass this error back to the template
                print(f"Parser Error: {parser.error}")
                pass

            return redirect('manage_doctrines')

    categories = DoctrineCategory.objects.all()
    fits = DoctrineFit.objects.select_related('category', 'ship_type').order_by('-created_at')

    context = {
        'categories': categories,
        'fits': fits,
        # FIX: Ensure we tell the template which base to use
        'base_template': get_template_base(request)
    }
    
    # Add sidebar permissions context
    context.update(get_mgmt_context(request.user))
    
    return render(request, 'management/doctrines.html', context)