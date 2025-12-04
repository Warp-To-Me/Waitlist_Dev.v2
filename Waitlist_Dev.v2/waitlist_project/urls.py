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
    
    # Roles Management
    path('management/roles/', core_views.management_roles, name='management_roles'),
    path('api/mgmt/search_users/', core_views.api_search_users, name='api_search_users'),
    path('api/mgmt/user_roles/<int:user_id>/', core_views.api_get_user_roles, name='api_get_user_roles'),
    path('api/mgmt/update_role/', core_views.api_update_user_role, name='api_update_user_role'),

    # --- Public Area ---
    path('', core_views.landing_page, name='landing_page'),
    path('profile/', core_views.profile_view, name='profile'),
    
    # Character Switching Routes
    path('profile/switch/<int:char_id>/', core_views.switch_character, name='switch_character'),
    path('profile/make_main/<int:char_id>/', core_views.make_main, name='make_main'),
    
    # API Routes
    path('api/refresh_profile/<int:char_id>/', core_views.api_refresh_profile, name='api_refresh_profile'),

    # --- INCLUDES ---
    # ESI Auth Routes (Login/Logout)
    path('', include('esi_auth.urls')),
    
    # Waitlist Data (Doctrines) -> THIS WAS MISSING
    path('', include('waitlist_data.urls')),
]