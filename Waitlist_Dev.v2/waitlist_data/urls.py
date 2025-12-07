from django.urls import path
from . import views

urlpatterns = [
    # DOCTRINES
    path('doctrines/', views.doctrine_list, name='doctrine_list'),
    path('doctrines/api/<int:fit_id>/', views.doctrine_detail_api, name='doctrine_detail_api'),
    path('management/doctrines/', views.manage_doctrines, name='manage_doctrines'),

    # WAITLIST / FLEET
    path('fleet/<int:fleet_id>/dashboard/', views.fleet_dashboard, name='fleet_dashboard'),
    path('fleet/<int:fleet_id>/xup/', views.x_up_submit, name='x_up_submit'),
    path('fleet/action/<int:entry_id>/<str:action>/', views.fc_action, name='fc_action'),
    path('fleet/<int:fleet_id>/take_command/', views.take_fleet_command, name='take_fleet_command'),
    
    # NEW: Fleet Overview API
    path('fleet/<int:fleet_id>/overview/', views.fleet_overview_api, name='fleet_overview_api'),
]