from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from ..models import DoctrineCategory, DoctrineFit

@require_GET
def doctrines_public_api(request):
    """
    Returns public doctrine data as JSON for the React frontend.
    """
    categories = DoctrineCategory.objects.all().order_by('order')
    data = []

    for cat in categories:
        # Get active fits for this category
        fits = cat.fits.filter(is_active=True).order_by('order')
        fit_list = []
        
        for fit in fits:
            fit_list.append({
                'id': fit.id,
                'name': fit.name,
                'role': fit.role,  # e.g., 'Logistics', 'DPS'
                'description': fit.description,
                'price_estimate': fit.price_estimate,
                'is_primary': fit.is_primary,
                # Add tags if you have a tagging system
                # 'tags': [tag.name for tag in fit.tags.all()] 
            })

        if fits.exists():
            data.append({
                'id': cat.id,
                'name': cat.name,
                'description': cat.description,
                'fits': fit_list
            })

    return JsonResponse({'categories': data})