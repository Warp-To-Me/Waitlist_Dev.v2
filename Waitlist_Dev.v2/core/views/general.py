from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Ban

def index(request):
    return render(request, 'landing.html')

@login_required
def access_denied(request):
    return render(request, 'access_denied.html')

@login_required
def banned(request):
    # Check if the user is actually banned to display relevant info
    ban_reason = None
    if hasattr(request.user, 'ban'):
        ban_reason = request.user.ban.reason
        
    context = {
        'ban_reason': ban_reason
    }
    return render(request, 'banned.html', context)