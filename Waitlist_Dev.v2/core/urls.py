from django.urls import path
from . import views, views_profile, views_management, views_rules, views_srp

app_name = 'core'

urlpatterns = [
    # --- Landing & General ---
    path('', views.index, name='home'),
    path('access-denied/', views.access_denied, name='access_denied'),
    path('banned/', views.banned, name='banned'),

    # --- Profile ---
    path('profile/', views_profile.profile_view, name='profile'),

    # --- Rules ---
    path('rules/', views_rules.rules_view, name='rules'),

    # --- SRP (Ship Replacement Program) ---
    path('srp/', views_srp.dashboard, name='srp_dashboard'),
    # Assuming request_view exists in views_srp based on typical patterns
    # path('srp/request/', views_srp.request_view, name='srp_request'),

    # --- Management Dashboard ---
    path('management/', views_management.dashboard, name='management_dashboard'),
    
    # Management: Users & Permissions
    path('management/users/', views_management.users_view, name='management_users'),
    path('management/roles/', views_management.roles_view, name='management_roles'),
    path('management/permissions/', views_management.permissions_view, name='management_permissions'),

    # Management: Bans
    path('management/bans/', views_management.bans_view, name='management_bans'),
    path('management/bans/audit/', views_management.ban_audit_view, name='management_ban_audit'),

    # Management: Fleet & Doctrines
    path('management/fleets/', views_management.fleets_view, name='management_fleets'),
    path('management/fleet-setup/', views_management.fleet_setup_view, name='management_fleet_setup'),
    path('management/fleet-settings/', views_management.fleet_settings_view, name='management_fleet_settings'),
    path('management/doctrines/', views_management.doctrines_view, name='management_doctrines'),
    path('management/skills/', views_management.skill_requirements_view, name='management_skills'),
    path('management/srp-config/', views_management.srp_config_view, name='management_srp_config'),

    # Management: System & Logs
    path('management/history/', views_management.history_view, name='management_history'),
    path('management/sde/', views_management.sde_view, name='management_sde'),
    path('management/celery/', views_management.celery_status, name='management_celery'),
    path('management/rules-helper/', views_management.rules_helper, name='management_rules_helper'),
]