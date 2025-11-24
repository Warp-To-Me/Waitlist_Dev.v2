def navbar_context(request):
    """
    Adds 'navbar_char' to every template context.
    Determines which character to display in the top navigation bar based on:
    1. Session (Active switch)
    2. 'is_main' database flag
    3. Fallback to first available character
    """
    if not request.user.is_authenticated:
        return {}
    
    # Get all characters efficiently
    # Note: For high traffic, we might cache this or rely on prefetch_related in views
    characters = request.user.characters.all()
    
    if not characters.exists():
        return {'navbar_char': None}

    navbar_char = None
    
    # 1. Check Session (User switched via Profile page)
    active_id = request.session.get('active_char_id')
    if active_id:
        navbar_char = characters.filter(character_id=active_id).first()
        
    # 2. Check Database Main
    if not navbar_char:
        navbar_char = characters.filter(is_main=True).first()
        
    # 3. Fallback
    if not navbar_char:
        navbar_char = characters.first()
        
    return {'navbar_char': navbar_char}