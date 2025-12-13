from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def rules_view(request):
    # Retrieve dynamic rules if they are stored in DB, otherwise render static template
    return render(request, 'base_content.html', {'title': 'Rules', 'content': 'Rules go here.'})