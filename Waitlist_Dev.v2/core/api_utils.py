from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from core.context_processors import navbar_context

@api_view(['GET'])
def api_me(request):
    """
    Returns global context for the user (Auth status, Theme, Characters, Permissions).
    Replaces 'navbar_context' context processor.
    """
    if not request.user.is_authenticated:
        return Response(None)
    
    # Get standard context
    ctx = navbar_context(request)
    
    # Serialize the character
    char_data = None
    if ctx.get('navbar_char'):
        c = ctx['navbar_char']
        char_data = {
            'character_id': c.character_id,
            'character_name': c.character_name,
            'is_main': c.is_main
        }
        
    return Response({
        'username': request.user.username,
        'is_staff': request.user.is_staff,
        'is_superuser': request.user.is_superuser,
        'is_management': ctx.get('user_is_management', False),
        'navbar_char': char_data,
        # Theme is handled by cookie on client side, but we could return pref here if stored in DB
    })