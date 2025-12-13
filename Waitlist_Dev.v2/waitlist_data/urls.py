from django.urls import path
from .views import dashboard, doctrines, fleet_setup, fleet_settings, api, actions

app_name = 'waitlist_data'

urlpatterns = [
    # --- Dashboard ---
    path('dashboard/', dashboard.fleet_dashboard, name='dashboard'),

    # --- Doctrines ---
    path('doctrines/', doctrines.doctrine_list, name='doctrines_list'),
    path('doctrines/<int:doctrine_id>/', doctrines.doctrine_detail_api, name='doctrine_detail'),

    # --- Fleet Management (FC Views) ---
    path('fleet/setup/', fleet_setup.fleet_setup, name='fleet_setup'),
    path('fleet/settings/', fleet_settings.fleet_settings, name='fleet_settings'),

    # --- Actions (User Interactions) ---
    path('action/join/', actions.x_up_submit, name='join_waitlist'),
    path('action/leave/', actions.leave_fleet, name='leave_waitlist'),
    path('action/xup/', actions.x_up_submit, name='x_up'),

    # --- API Endpoints ---

]