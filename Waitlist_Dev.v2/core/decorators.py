from functools import wraps
from django.shortcuts import redirect
from django.utils import timezone
from django.db import models
from core.models import Ban

def check_ban_status(view_func):
    """
    Decorator that checks if the user is banned.
    If banned, redirects to the 'banned' page unless they are already there.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            # Check for any active ban
            active_ban = Ban.objects.filter(
                user=request.user
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            ).first()

            if active_ban:
                return redirect('banned_view')

        return view_func(request, *args, **kwargs)
    return _wrapped_view
