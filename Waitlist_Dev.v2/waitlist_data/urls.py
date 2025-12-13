from django.urls import path
from .views import doctrines, fleet_setup, fleet_settings, dashboard, actions

urlpatterns = [
    # DOCTRINES
    path('doctrines/', doctrines.doctrine_list, name='doctrine_list'),
    path('doctrines/skills/', doctrines.public_skill_requirements, name='doctrine_skills'),
    path('doctrines/api/<int:fit_id>/', doctrines.doctrine_detail_api, name='doctrine_detail_api'),
    
    # MANAGEMENT
    path('management/doctrines/', doctrines.manage_doctrines, name='manage_doctrines'),
    path('management/skills/', doctrines.manage_skill_requirements, name='management_skills'),
    
    # SKILL API
    path('api/skills/add/', doctrines.api_skill_req_add, name='api_skill_req_add'),
    path('api/skills/delete/', doctrines.api_skill_req_delete, name='api_skill_req_delete'),
    path('api/skills/search_hull/', doctrines.api_search_hull, name='api_search_hull'),
    
    # GROUP ROUTES
    path('api/skills/group/manage/', doctrines.api_skill_group_manage, name='api_skill_group_manage'),
    path('api/skills/group/member/add/', doctrines.api_skill_group_member_add, name='api_skill_group_member_add'),
    path('api/skills/group/member/remove/', doctrines.api_skill_group_member_remove, name='api_skill_group_member_remove'),

    # TIER ROUTES
    path('api/skills/tier/manage/', doctrines.api_skill_tier_manage, name='api_skill_tier_manage'),

    path('api/doctrines/export/', doctrines.api_export_doctrines, name='api_export_doctrines'),
    path('api/doctrines/import/', doctrines.api_import_doctrines, name='api_import_doctrines'),

    # FLEET SETUP & TEMPLATES
    path('fleet/setup/', fleet_setup.fleet_setup, name='fleet_setup'),
    path('api/fleet/template/save/', fleet_setup.api_save_structure_template, name='api_save_structure_template'),
    path('api/fleet/template/delete/', fleet_setup.api_delete_structure_template, name='api_delete_structure_template'),
    path('api/fleet/create_structured/', fleet_setup.api_create_fleet_with_structure, name='api_create_fleet_with_structure'),

    # FLEET SETTINGS
    path('fleet/<uuid:token>/settings/', fleet_settings.fleet_settings, name='fleet_settings'),
    path('fleet/<uuid:token>/api/settings/', fleet_settings.api_update_fleet_settings, name='api_update_fleet_settings'),
    path('api/fleet/close/<uuid:token>/', fleet_settings.api_close_fleet, name='api_close_fleet'),
    path('api/fleet/link/<uuid:token>/', fleet_settings.api_link_esi_fleet, name='api_link_esi_fleet'), 

    # WAITLIST / FLEET DASHBOARD
    path('fleet/<uuid:token>/dashboard/', dashboard.fleet_dashboard, name='fleet_dashboard'),
    path('fleet/<uuid:token>/history/', dashboard.fleet_history_view, name='fleet_history'), 
    path('fleet/<uuid:token>/overview/', dashboard.fleet_overview_api, name='fleet_overview_api'),
    
    # ACTIONS
    path('fleet/<uuid:token>/xup/', actions.x_up_submit, name='x_up_submit'),
    path('fleet/<uuid:token>/take_command/', fleet_settings.take_fleet_command, name='take_fleet_command'),
    
    # Internal Actions
    path('fleet/action/<int:entry_id>/<str:action>/', actions.fc_action, name='fc_action'),
    path('fleet/entry/<int:entry_id>/leave/', actions.leave_fleet, name='leave_fleet'),
    path('fleet/entry/<int:entry_id>/update/', actions.update_fit, name='update_fit'),
    path('fleet/entry/api/<int:entry_id>/', actions.api_entry_details, name='api_entry_details'),
    
    # History API
    path('fleet/history/api/<int:log_id>/', actions.api_history_fit_details, name='api_history_fit_details'),
]