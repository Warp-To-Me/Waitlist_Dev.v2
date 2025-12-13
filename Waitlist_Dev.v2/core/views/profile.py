from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import EveCharacter
from core.utils import get_main_character

@login_required
def profile_view(request):
    user = request.user
    characters = EveCharacter.objects.filter(user=user)
    main_char = get_main_character(user)
    
    context = {
        'user': user,
        'characters': characters,
        'main_character': main_char,
    }
    return render(request, 'profile.html', context)