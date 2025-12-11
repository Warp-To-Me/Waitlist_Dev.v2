from django.contrib import admin
from django.urls import path, include
from core import views as core_views
from core import views_management, views_profile, views_rules, views_srp

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # --- SRP MANAGEMENT ---
    path('management/srp/config/', views_srp.srp_config, name='srp_config'),
    path('api/mgmt/srp/set_source/', views_srp.api_set_srp_source, name='api_set_srp_source'),
    path('api/mgmt/srp/sync/', views_srp.api_sync_srp, name='api_sync_srp'),
    path('api/mgmt/srp/update_category/', views_srp.api_update_transaction_category, name='api_update_transaction_category'),
    
    # --- SRP DASHBOARD ---
    path('srp/dashboard/', views_srp.srp_dashboard, name='srp_dashboard'),
    path('api/srp/data/', views_srp.api_srp_data, name='api_srp_data'),
    path('api/srp/status/', views_srp.api_srp_status, name='api_srp_status'),
    
    # --- CORE MANAGEMENT ---
    path('management/', views_management.management_dashboard, name='custom_admin'),
    path('management/users/', views_management.management_users, name='management_users'),
    path('management/users/<int:user_id>/inspect/', views_management.management_user_inspect, name='management_user_inspect'),
    path('management/users/<int:user_id>/inspect/<int:char_id>/', views_management.management_user_inspect, name='management_user_inspect_char'),

    path('management/fleets/', views_management.management_fleets, name='management_fleets'),
    path('management/sde/', views_management.management_sde, name='management_sde'),
    path('management/system/', views_management.management_celery, name='management_celery'),
    path('management/permissions/', views_management.management_permissions, name='management_permissions'),

    # Ban Management
    path('management/bans/', views_management.management_bans, name='management_bans'),
    path('management/bans/audit/', views_management.management_ban_audit, name='management_ban_audit'),
    path('api/mgmt/bans/add/', views_management.api_ban_user, name='api_ban_user'),
    path('api/mgmt/bans/update/', views_management.api_update_ban, name='api_update_ban'),
    
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

    # --- RULE MANAGER ---
    path('management/rules/', views_rules.management_rules, name='management_rules'),
    path('api/mgmt/rules/search/', views_rules.api_group_search, name='api_group_search'),
    path('api/mgmt/rules/list/', views_rules.api_list_configured_groups, name='api_list_configured_groups'),
    path('api/mgmt/rules/discovery/<int:group_id>/', views_rules.api_rule_discovery, name='api_rule_discovery'),
    path('api/mgmt/rules/save/', views_rules.api_save_rules, name='api_save_rules'),
    path('api/mgmt/rules/delete/', views_rules.api_delete_rules, name='api_delete_rules'),
    path('api/mgmt/rules/export/', views_rules.api_export_rules, name='api_export_rules'),
    path('api/mgmt/rules/import/', views_rules.api_import_rules, name='api_import_rules'),

    # --- PROFILE & PUBLIC ---
    path('', core_views.landing_page, name='landing_page'),
    path('banned/', core_views.banned_view, name='banned_view'),
    path('profile/', views_profile.profile_view, name='profile'),
    path('profile/switch/<int:char_id>/', views_profile.switch_character, name='switch_character'),
    path('profile/make_main/<int:char_id>/', views_profile.make_main, name='make_main'),
    
    path('api/refresh_profile/<int:char_id>/', views_profile.api_refresh_profile, name='api_refresh_profile'),
    path('api/profile/status/<int:char_id>/', views_profile.api_pilot_status, name='api_pilot_status'), # NEW
    
    path('api/profile/toggle_visibility/', views_profile.api_toggle_xup_visibility, name='api_toggle_xup_visibility'),
    
    path('access-denied/', core_views.access_denied, name='access_denied'),

    # Includes
    path('', include('esi_auth.urls')),
    path('', include('waitlist_data.urls')),
]