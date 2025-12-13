from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
# Import from core app
from core.models import SRPConfiguration
# If you have SRP models/forms, import them here. 
# Assuming standard imports based on migration:

@login_required
def dashboard(request):
    # SRP Dashboard logic
    return render(request, 'srp/dashboard.html')

@login_required
def request_view(request):
    if request.method == 'POST':
        # Handle SRP request submission
        messages.success(request, "SRP Request submitted.")
        return redirect('core:srp_dashboard')
    
    return render(request, 'srp/request.html')