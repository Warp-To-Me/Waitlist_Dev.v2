from django.contrib import admin
from django.urls import path, include

# New Modular Imports
from core import views as core_views
from core import views_management, views_profile, views_rules, views_srp # Added views_srp

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # --- CORE MANAGEMENT (views_management.py) ---
    path('management/', views_management.management_dashboard, name='custom_admin'),
    path('management/users/', views_management.management_users, name='management_users'),
    path('management/users/<int:user_id>/inspect/', views_management.management_user_inspect, name='management_user_inspect'),
    path('management/users/<int:user_id>/inspect/<int:char_id>/', views_management.management_user_inspect, name='management_user_inspect_char'),

    path('management/fleets/', views_management.management_fleets, name='management_fleets'),
    path('management/sde/', views_management.management_sde, name='management_sde'),
    path('management/system/', views_management.management_celery, name='management_celery'),
    path('management/permissions/', views_management.management_permissions, name='management_permissions'),

    # --- SRP MANAGEMENT ---
    path('management/srp/config/', views_srp.srp_config, name='srp_config'),
    path('api/mgmt/srp/set_source/', views_srp.api_set_srp_source, name='api_set_srp_source'),
    path('api/mgmt/srp/sync/', views_srp.api_sync_srp, name='api_sync_srp'),
    
    # --- SRP DASHBOARD ---
    path('srp/dashboard/', views_srp.srp_dashboard, name='srp_dashboard'),
    path('api/srp/data/', views_srp.api_srp_data, name='api_srp_data'),
    
    # Roles API
    path('management/roles/', views_management.management_roles, name='management_roles'),
    path('api/mgmt/search_users/', views_management.api_search_users, name='api_search_users'),
    path('api/mgmt/user_roles/<int:user_id>/', views_management.api_get_user_roles, name='api_get_user_roles'),
    path('api/mgmt/update_role/', views_management.api_update_user_role, name='api_update_user_role'),
    path('api/mgmt/roles/reorder/', views_management.api_reorder_roles, name='api_reorder_roles'),
    path('api/mgmt/permissions/toggle/', views_management.api_permissions_toggle, name='api_permissions_toggle'),
    path('api/mgmt/groups/', views_management.api_manage_group, name='api_manage_group'),
    path('api/mgmt/unlink_alt/', views_management.api_unlink_alt, name='api_unlink_alt'),
    path('api/mgmt/promote_alt/', views_management.api_promote_alt, name='api_promote_alt'),

    # --- RULE MANAGER (views_rules.py) ---
    path('management/rules/', views_rules.management_rules, name='management_rules'),
    path('api/mgmt/rules/search/', views_rules.api_group_search, name='api_group_search'),
    path('api/mgmt/rules/list/', views_rules.api_list_configured_groups, name='api_list_configured_groups'),
    path('api/mgmt/rules/discovery/<int:group_id>/', views_rules.api_rule_discovery, name='api_rule_discovery'),
    path('api/mgmt/rules/save/', views_rules.api_save_rules, name='api_save_rules'),
    path('api/mgmt/rules/delete/', views_rules.api_delete_rules, name='api_delete_rules'),
    path('api/mgmt/rules/export/', views_rules.api_export_rules, name='api_export_rules'),
    path('api/mgmt/rules/import/', views_rules.api_import_rules, name='api_import_rules'),

    # --- PROFILE & PUBLIC (views_profile.py & views.py) ---
    path('', core_views.landing_page, name='landing_page'),
    path('profile/', views_profile.profile_view, name='profile'),
    path('profile/switch/<int:char_id>/', views_profile.switch_character, name='switch_character'),
    path('profile/make_main/<int:char_id>/', views_profile.make_main, name='make_main'),
    path('api/refresh_profile/<int:char_id>/', views_profile.api_refresh_profile, name='api_refresh_profile'),
    path('api/profile/toggle_visibility/', views_profile.api_toggle_xup_visibility, name='api_toggle_xup_visibility'), # NEW
    
    path('access-denied/', core_views.access_denied, name='access_denied'),

    # Includes
    path('', include('esi_auth.urls')),
    path('', include('waitlist_data.urls')),
]