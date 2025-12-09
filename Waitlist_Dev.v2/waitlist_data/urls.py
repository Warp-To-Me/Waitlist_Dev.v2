from django.urls import path
from . import views

urlpatterns = [
    # DOCTRINES
    path('doctrines/', views.doctrine_list, name='doctrine_list'),
    path('doctrines/api/<int:fit_id>/', views.doctrine_detail_api, name='doctrine_detail_api'),
    path('management/doctrines/', views.manage_doctrines, name='manage_doctrines'),

    # NEW: FLEET SETUP & TEMPLATES
    path('fleet/setup/', views.fleet_setup, name='fleet_setup'),
    path('api/fleet/template/save/', views.api_save_structure_template, name='api_save_structure_template'),
    path('api/fleet/template/delete/', views.api_delete_structure_template, name='api_delete_structure_template'),
    path('api/fleet/create_structured/', views.api_create_fleet_with_structure, name='api_create_fleet_with_structure'),

    # NEW: FLEET SETTINGS
    path('fleet/<uuid:token>/settings/', views.fleet_settings, name='fleet_settings'),
    path('fleet/<uuid:token>/api/settings/', views.api_update_fleet_settings, name='api_update_fleet_settings'),
    path('api/fleet/close/<uuid:token>/', views.api_close_fleet, name='api_close_fleet'), # NEW

    # WAITLIST / FLEET
    path('fleet/<uuid:token>/dashboard/', views.fleet_dashboard, name='fleet_dashboard'),
    path('fleet/<uuid:token>/history/', views.fleet_history_view, name='fleet_history'), 
    path('fleet/<uuid:token>/xup/', views.x_up_submit, name='x_up_submit'),
    path('fleet/<uuid:token>/take_command/', views.take_fleet_command, name='take_fleet_command'),
    
    # Internal Actions
    path('fleet/action/<int:entry_id>/<str:action>/', views.fc_action, name='fc_action'),
    path('fleet/entry/<int:entry_id>/leave/', views.leave_fleet, name='leave_fleet'),
    path('fleet/entry/<int:entry_id>/update/', views.update_fit, name='update_fit'),
    path('fleet/<uuid:token>/overview/', views.fleet_overview_api, name='fleet_overview_api'),
    path('fleet/entry/api/<int:entry_id>/', views.api_entry_details, name='api_entry_details'),
    
    # History API
    path('fleet/history/api/<int:log_id>/', views.api_history_fit_details, name='api_history_fit_details'),
]