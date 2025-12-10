from django.contrib import admin
from django.urls import path, include
from core import views as core_views
from core import views_management, views_profile, views_rules, views_srp # Added views_srp

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # --- SRP MANAGEMENT ---
    path('management/srp/config/', views_srp.srp_config, name='srp_config'),
    path('api/mgmt/srp/set_source/', views_srp.api_set_srp_source, name='api_set_srp_source'),
    path('api/mgmt/srp/sync/', views_srp.api_sync_srp, name='api_sync_srp'),
    
    # --- SRP DASHBOARD ---
    path('srp/dashboard/', views_srp.srp_dashboard, name='srp_dashboard'),
    path('api/srp/data/', views_srp.api_srp_data, name='api_srp_data'),
    
    # Public
    path('', core_views.landing_page, name='landing_page'),
    
    # Include ESI Auth URLs
    path('auth/', include('esi_auth.urls')),
]