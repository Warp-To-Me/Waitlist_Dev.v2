from core.utils import ROLE_HIERARCHY

def navbar_context(request):
    """
    Adds 'navbar_char', 'user_is_management', and 'current_theme' to every template context.
    """
    context = {}
    
    # --- 3. Theme Logic (New) ---
    # Default to 'default' if no cookie is set
    context['current_theme'] = request.COOKIES.get('site_theme', 'default')
    
    if not request.user.is_authenticated:
        return context
    
    # --- 1. Navbar Character Logic ---
    characters = request.user.characters.all()
    
    navbar_char = None
    if characters.exists():
        # Check Session
        active_id = request.session.get('active_char_id')
        if active_id:
            navbar_char = characters.filter(character_id=active_id).first()
        
        # Check Database Main
        if not navbar_char:
            navbar_char = characters.filter(is_main=True).first()
            
        # Fallback
        if not navbar_char:
            navbar_char = characters.first()
            
    context['navbar_char'] = navbar_char

    # --- 2. Management Permission Logic ---
    # Check if user is Superuser OR has a role in the Management tier (Resident+)
    if request.user.is_superuser:
        context['user_is_management'] = True
    else:
        # ROLE_HIERARCHY[:-2] excludes 'Pilot' and 'Public'
        allowed_roles = ROLE_HIERARCHY[:-2]
        context['user_is_management'] = request.user.groups.filter(name__in=allowed_roles).exists()

    return context