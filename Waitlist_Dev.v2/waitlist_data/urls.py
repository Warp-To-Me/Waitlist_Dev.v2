from django.urls import path
from . import views

urlpatterns = [
    # DOCTRINES
    path('doctrines/', views.doctrine_list, name='doctrine_list'),
    path('doctrines/api/<int:fit_id>/', views.doctrine_detail_api, name='doctrine_detail_api'),
    path('management/doctrines/', views.manage_doctrines, name='manage_doctrines'),

    # WAITLIST / FLEET (Updated to use UUID tokens)
    path('fleet/<uuid:token>/dashboard/', views.fleet_dashboard, name='fleet_dashboard'),
    path('fleet/<uuid:token>/xup/', views.x_up_submit, name='x_up_submit'),
    path('fleet/<uuid:token>/take_command/', views.take_fleet_command, name='take_fleet_command'),
    
    # Internal Actions still use integer IDs for simplicity where not exposed in the main URL bar
    path('fleet/action/<int:entry_id>/<str:action>/', views.fc_action, name='fc_action'),
    
    # Fleet Overview API (uses integer ID internally, but could be switched. 
    # For now, we'll keep ID here as it's an AJAX endpoint, or switch if needed. 
    # Let's switch it to token for consistency).
    path('fleet/<uuid:token>/overview/', views.fleet_overview_api, name='fleet_overview_api'),
    
    path('fleet/entry/api/<int:entry_id>/', views.api_entry_details, name='api_entry_details'),
]