from django.contrib import admin
from django.urls import path, include, re_path
from core import views as core_views
from core import views_management, views_profile, views_rules, views_srp, views_frontend, api_utils, views_skills
from core.views_command import api_command_workflow, api_command_workflow_step, api_command_workflow_detail
from waitlist_data.views import fleet_setup, fleet_settings, dashboard, actions

# Define API patterns first
api_urlpatterns = [
    # Global Context
    path('me/', api_utils.api_me, name='api_me'),

    # --- SRP MANAGEMENT ---
    path('management/srp/config/', views_srp.srp_config, name='srp_config'),
    path('mgmt/srp/set_source/', views_srp.api_set_srp_source, name='api_set_srp_source'),
    path('mgmt/srp/sync/', views_srp.api_sync_srp, name='api_sync_srp'),
    path('mgmt/srp/update_category/', views_srp.api_update_transaction_category, name='api_update_transaction_category'),
    path('mgmt/srp/divisions/', views_srp.api_divisions, name='api_divisions'),
    
    # --- SRP DASHBOARD ---
    path('srp/dashboard/', views_srp.srp_dashboard, name='srp_dashboard'),
    path('srp/data/', views_srp.api_srp_data, name='api_srp_data'),
    path('srp/status/', views_srp.api_srp_status, name='api_srp_status'),
    
    # --- CORE MANAGEMENT ---
    path('management/', views_management.management_dashboard, name='management_dashboard'),
    path('management/users/', views_management.management_users, name='management_users'),
    path('management/users/<int:user_id>/inspect/', views_management.management_user_inspect, name='management_user_inspect'),
    path('management/users/<int:user_id>/inspect/<int:char_id>/', views_management.management_user_inspect, name='management_user_inspect_char'),

    path('management/fleets/', views_management.management_fleets, name='management_fleets'),
    
    # --- FLEET MANAGEMENT (REACT) ---
    path('management/fleets/setup/init/', fleet_setup.api_fleet_setup_init, name='api_fleet_setup_init'),
    path('management/fleets/create_structured/', fleet_setup.api_create_fleet_with_structure, name='api_create_fleet_with_structure'),
    path('management/fleets/templates/save/', fleet_setup.api_save_structure_template, name='api_save_structure_template'),
    path('management/fleets/templates/delete/', fleet_setup.api_delete_structure_template, name='api_delete_structure_template'),
    
    path('management/fleets/<uuid:token>/settings/', fleet_settings.api_get_fleet_settings, name='api_get_fleet_settings'),
    path('management/fleets/<uuid:token>/update_settings/', fleet_settings.api_update_fleet_settings, name='api_update_fleet_settings'),
    path('management/fleets/<uuid:token>/link_esi/', fleet_settings.api_link_esi_fleet, name='api_link_esi_fleet'),
    path('management/fleets/<uuid:token>/close/', fleet_settings.api_close_fleet, name='api_close_fleet'),
    path('management/fleets/<uuid:token>/take_over/', fleet_settings.api_take_over_fleet, name='api_take_over_fleet'),
    
    path('management/fleets/<uuid:token>/history/', dashboard.fleet_history_view, name='fleet_history_api'),
    path('management/fleets/history/api/<int:log_id>/', actions.api_history_fit_details, name='api_history_fit_details'),

    path('management/sde/', views_management.management_sde, name='management_sde'),
    path('management/system/', views_management.management_celery, name='management_celery'),
    path('management/permissions/', views_management.management_permissions, name='management_permissions'),

    # Ban Management
    path('management/bans/', views_management.management_bans, name='management_bans'),
    path('management/bans/audit/', views_management.management_ban_audit, name='management_ban_audit'),
    path('mgmt/bans/add/', views_management.api_ban_user, name='api_ban_user'),
    path('mgmt/bans/update/', views_management.api_update_ban, name='api_update_ban'),
    
    # Script Management
    path('mgmt/scripts/', views_management.management_scripts, name='management_scripts'),
    path('mgmt/scripts/run/', views_management.api_run_script, name='api_run_script'),
    path('mgmt/scripts/stop/', views_management.api_stop_script, name='api_stop_script'),

    # Roles API
    path('management/roles/', views_management.management_roles, name='management_roles'),
    path('mgmt/search_users/', views_management.api_search_users, name='api_search_users'),
    path('mgmt/user_roles/<int:user_id>/', views_management.api_get_user_roles, name='api_get_user_roles'),
    path('mgmt/update_role/', views_management.api_update_user_role, name='api_update_user_role'),
    path('mgmt/roles/reorder/', views_management.api_reorder_roles, name='api_reorder_roles'),
    path('mgmt/permissions/toggle/', views_management.api_permissions_toggle, name='api_permissions_toggle'),
    path('mgmt/groups/', views_management.api_manage_group, name='api_manage_group'),
    path('mgmt/unlink_alt/', views_management.api_unlink_alt, name='api_unlink_alt'),
    path('mgmt/promote_alt/', views_management.api_promote_alt, name='api_promote_alt'),

    # --- COMMAND WORKFLOW ---
    path('management/command/', api_command_workflow, name='api_command_workflow'),
    path('management/command/<int:entry_id>/', api_command_workflow_detail, name='api_command_workflow_detail'),
    path('management/command/<int:entry_id>/step/', api_command_workflow_step, name='api_command_workflow_step'),

    # --- RULE MANAGER ---
    path('management/rules/', views_rules.management_rules, name='management_rules'),
    # Alias paths for React Frontend which uses /api/management/rules/*
    path('management/rules/search_groups/', views_rules.api_group_search, name='api_group_search_alias'),
    path('management/rules/list/', views_rules.api_list_configured_groups, name='api_list_configured_groups_alias'),
    path('management/rules/discovery/<int:group_id>/', views_rules.api_rule_discovery, name='api_rule_discovery_alias'),
    path('management/rules/save/', views_rules.api_save_rules, name='api_save_rules_alias'),
    path('management/rules/delete/', views_rules.api_delete_rules, name='api_delete_rules_alias'),
    path('management/rules/export/', views_rules.api_export_rules, name='api_export_rules_alias'),
    path('management/rules/import/', views_rules.api_import_rules, name='api_import_rules_alias'),
    
    # Original paths (kept for compatibility or internal links)
    path('mgmt/rules/search/', views_rules.api_group_search, name='api_group_search'),
    path('mgmt/rules/list/', views_rules.api_list_configured_groups, name='api_list_configured_groups'),
    path('mgmt/rules/discovery/<int:group_id>/', views_rules.api_rule_discovery, name='api_rule_discovery'),
    path('mgmt/rules/save/', views_rules.api_save_rules, name='api_save_rules'),
    path('mgmt/rules/delete/', views_rules.api_delete_rules, name='api_delete_rules'),
    path('mgmt/rules/export/', views_rules.api_export_rules, name='api_export_rules'),
    path('mgmt/rules/import/', views_rules.api_import_rules, name='api_import_rules'),

    # --- PROFILE & PUBLIC ---
    path('landing/', core_views.landing_page, name='landing_page_api'),
    path('banned/', core_views.banned_view, name='banned_view_api'),
    path('profile/', views_profile.profile_view, name='profile_api'),
    path('profile/switch/<int:char_id>/', views_profile.switch_character, name='switch_character'),
    path('profile/make_main/<int:char_id>/', views_profile.make_main, name='make_main'),
    
    path('refresh_profile/<int:char_id>/', views_profile.api_refresh_profile, name='api_refresh_profile'),
    path('profile/status/<int:char_id>/', views_profile.api_pilot_status, name='api_pilot_status'), 
    
    path('profile/toggle_visibility/', views_profile.api_toggle_xup_visibility, name='api_toggle_xup_visibility'),
    path('profile/toggle_aggregate/', views_profile.api_toggle_aggregate_setting, name='api_toggle_aggregate_setting'),
    
    # Doctrines API
    path('doctrines/', core_views.doctrine_list, name='doctrine_list_api'),
    path('doctrines/fit/<int:fit_id>/', core_views.doctrine_detail_api, name='doctrine_detail_api'),
    path('doctrines/manage/', core_views.manage_doctrines, name='manage_doctrines_api'),

    # --- DOCTRINE MANAGEMENT (Frontend Matches) ---
    path('management/doctrines/data/', core_views.api_doctrine_data, name='api_doctrine_data'),
    path('management/doctrines/save/', core_views.api_doctrine_save, name='api_doctrine_save'),
    path('management/doctrines/export/', core_views.api_doctrine_export, name='api_doctrine_export'),
    path('management/doctrines/import/', core_views.api_doctrine_import, name='api_doctrine_import'),

    # --- SKILLS MANAGEMENT ---
    path('management/skills/data/', views_skills.api_skills_data, name='api_skills_data'),
    path('search_hull/', views_skills.api_search_hull, name='api_search_hull'),
    path('skill_req/<str:action>/', views_skills.api_skill_req_manage, name='api_skill_req_manage'),
    path('skill_group/manage/', views_skills.api_skill_group_manage, name='api_skill_group_manage'),
    path('skill_group/<int:group_id>/members/', views_skills.api_skill_group_members, name='api_skill_group_members'),
    path('skill_group/member/<str:action>/', views_skills.api_skill_member_manage, name='api_skill_member_manage'),
    path('skill_tier/manage/', views_skills.api_skill_tier_manage, name='api_skill_tier_manage'),

    # Fleet API Overrides (Must come before waitlist_data.urls to take precedence if name conflicts, 
    # but waitlist_data.urls has the original paths. We should probably rely on waitlist_data.urls 
    # if we modified the views inside it directly.
    # I modified Waitlist_Dev.v2/waitlist_data/views/dashboard.py.
    # So I need to ensure the URL pointing to it is correct.)

    # Includes
    path('', include('waitlist_data.urls')),
]

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # API Routes
    path('api/', include(api_urlpatterns)),
    
    # Auth Routes (Keep these at root for EVE SSO callbacks unless we move them too)
    # The esi_auth app likely relies on specific callback URLs.
    path('', include('esi_auth.urls')),

    # Frontend Catch-All (Must be last)
    # Serves React for any path not matched above
    # We remove 'auth' from exclusion to allow /auth/login (React) to pass through, 
    # as specific backend auth routes are already matched above.
    re_path(r'^(?!api|admin|static|media|ws).*$', views_frontend.frontend_app, name='frontend_app'),
]
