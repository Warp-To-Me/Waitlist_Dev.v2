from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db.models import Q
from django.conf import settings

# Updated imports for new directory structure
from core.models import Ban, BanAuditLog, RolePriority
from core.decorators import staff_required, permission_required
from core.utils import get_main_character

# Import models from other apps as needed for management
from waitlist_data.models import DoctrineFit, DoctrineCategory, Fleet
from pilot_data.models import EveCharacter

# --- Dashboard ---
@login_required
@staff_required
def dashboard(request):
    return render(request, 'management/dashboard.html')

# --- Users & Permissions ---
@login_required
@staff_required
def users_view(request):
    users = User.objects.all().select_related('profile') # Assuming profile exists or similar
    return render(request, 'management/users.html', {'users': users})

@login_required
@staff_required
def roles_view(request):
    roles = Group.objects.all()
    return render(request, 'management/roles.html', {'roles': roles})

@login_required
@staff_required
def permissions_view(request):
    return render(request, 'management/permissions.html')

# --- Bans ---
@login_required
@staff_required
def bans_view(request):
    bans = Ban.objects.all().select_related('user', 'issuer')
    return render(request, 'management/bans.html', {'bans': bans})

@login_required
@staff_required
def ban_audit_view(request):
    logs = BanAuditLog.objects.all().order_by('-created_at')
    return render(request, 'management/ban_audit.html', {'logs': logs})

# --- Fleets & Doctrines ---
@login_required
@staff_required
def fleets_view(request):
    fleets = Fleet.objects.all().order_by('-start_time')
    return render(request, 'management/fleets.html', {'fleets': fleets})

@login_required
@staff_required
def fleet_setup_view(request):
    return render(request, 'management/fleet_setup.html')

@login_required
@staff_required
def fleet_settings_view(request):
    return render(request, 'management/fleet_settings.html')

@login_required
@staff_required
def doctrines_view(request):
    categories = DoctrineCategory.objects.all()
    fits = DoctrineFit.objects.all()
    return render(request, 'management/doctrines.html', {'categories': categories, 'fits': fits})

@login_required
@staff_required
def skill_requirements_view(request):
    return render(request, 'management/skill_requirements.html')

@login_required
@staff_required
def srp_config_view(request):
    return render(request, 'management/srp_config.html')

# --- System & History ---
@login_required
@staff_required
def history_view(request):
    return render(request, 'management/history.html')

@login_required
@staff_required
def sde_view(request):
    return render(request, 'management/sde.html')

@login_required
@staff_required
def celery_status(request):
    # This usually requires inspecting Celery/Redis
    return render(request, 'management/celery_status.html')

@login_required
@staff_required
def rules_helper(request):
    return render(request, 'management/rules_helper.html')