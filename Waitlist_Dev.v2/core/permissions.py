from core.models import Capability
from core.utils import ROLES_MANAGEMENT, ROLES_FC, ROLES_ADMIN

# --- Helper for SPA Rendering ---
def get_template_base(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return 'base_content.html'
    return 'base.html'

# --- Permission Helpers ---

def get_user_capabilities(user):
    """
    Returns a set of capability slugs for the user.
    """
    if user.is_superuser:
        return set(Capability.objects.values_list('slug', flat=True))
    
    return set(Capability.objects.filter(groups__user=user).values_list('slug', flat=True).distinct())

def is_management(user):
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='access_management').exists(): return True
    return user.groups.filter(name__in=ROLES_MANAGEMENT).exists()

def is_fleet_command(user):
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='access_fleet_command').exists(): return True
    return user.groups.filter(name__in=ROLES_FC).exists()

def is_admin(user):
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='access_admin').exists(): return True
    return user.groups.filter(name__in=ROLES_ADMIN).exists()

def can_manage_doctrines(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='manage_doctrines').exists()

def can_manage_analysis_rules(user):
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='manage_analysis_rules').exists()

def can_manage_roles(user):
    """
    Checks if user has permission to promote/demote others.
    """
    if user.is_superuser: return True
    if user.groups.filter(capabilities__slug='promote_demote_users').exists(): return True
    return user.groups.filter(name__in=ROLES_ADMIN).exists()

def can_view_fleet_overview(user):
    """
    Checks if user can see the live fleet composition sidebar (Resident+).
    """
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='view_fleet_overview').exists()

# --- NEW PERMISSION ---
def can_view_sensitive_data(user):
    """
    Checks if user can view unobfuscated financial/asset data (Admin or Personnel Manager).
    """
    if user.is_superuser: return True
    return user.groups.filter(capabilities__slug='view_sensitive_data').exists()

def get_mgmt_context(user):
    """
    Injects the granular permission set into the template.
    """
    perms = get_user_capabilities(user)
    return {
        'user_perms': perms,
        'can_view_fleets': 'access_fleet_command' in perms,
        'can_view_admin': 'access_admin' in perms,
        'is_fc': 'access_fleet_command' in perms
    }