from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # Custom Management (Core)
    path('management/', core_views.management_dashboard, name='custom_admin'),
    path('management/users/', core_views.management_users, name='management_users'),
    path('management/users/<int:user_id>/inspect/', core_views.management_user_inspect, name='management_user_inspect'),
    path('management/users/<int:user_id>/inspect/<int:char_id>/', core_views.management_user_inspect, name='management_user_inspect_char'),

    path('management/fleets/', core_views.management_fleets, name='management_fleets'),
    path('management/sde/', core_views.management_sde, name='management_sde'),
    path('management/system/', core_views.management_celery, name='management_celery'),
    path('management/permissions/', core_views.management_permissions, name='management_permissions'),
    
    # --- RULE MANAGER (NEW) ---
    path('management/rules/', core_views.management_rules, name='management_rules'),
    path('api/mgmt/rules/search/', core_views.api_group_search, name='api_group_search'),
    path('api/mgmt/rules/list/', core_views.api_list_configured_groups, name='api_list_configured_groups'),
    path('api/mgmt/rules/discovery/<int:group_id>/', core_views.api_rule_discovery, name='api_rule_discovery'),
    path('api/mgmt/rules/save/', core_views.api_save_rules, name='api_save_rules'),
    path('api/mgmt/rules/delete/', core_views.api_delete_rules, name='api_delete_rules'), # NEW

    # Roles Management
    path('management/roles/', core_views.management_roles, name='management_roles'),
    path('api/mgmt/search_users/', core_views.api_search_users, name='api_search_users'),
    path('api/mgmt/user_roles/<int:user_id>/', core_views.api_get_user_roles, name='api_get_user_roles'),
    path('api/mgmt/update_role/', core_views.api_update_user_role, name='api_update_user_role'),
    
    # Permission & Group API
    path('api/mgmt/permissions/toggle/', core_views.api_permissions_toggle, name='api_permissions_toggle'),
    path('api/mgmt/groups/', core_views.api_manage_group, name='api_manage_group'),
    path('api/mgmt/roles/reorder/', core_views.api_reorder_roles, name='api_reorder_roles'),

    # API Routes
    path('api/mgmt/unlink_alt/', core_views.api_unlink_alt, name='api_unlink_alt'),
    path('api/mgmt/promote_alt/', core_views.api_promote_alt, name='api_promote_alt'),

    # Public Area
    path('', core_views.landing_page, name='landing_page'),
    path('profile/', core_views.profile_view, name='profile'),
    
    # Character Switching
    path('profile/switch/<int:char_id>/', core_views.switch_character, name='switch_character'),
    path('profile/make_main/<int:char_id>/', core_views.make_main, name='make_main'),
    
    # API Routes
    path('api/refresh_profile/<int:char_id>/', core_views.api_refresh_profile, name='api_refresh_profile'),

    # Includes
    path('', include('esi_auth.urls')),
    path('', include('waitlist_data.urls')),
    path('access-denied/', core_views.access_denied, name='access_denied'),
]