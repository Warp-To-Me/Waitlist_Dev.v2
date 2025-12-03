from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Management Area ---
    path('management/', core_views.management_dashboard, name='custom_admin'),
    path('management/users/', core_views.management_users, name='management_users'),
    path('management/fleets/', core_views.management_fleets, name='management_fleets'),
    path('management/sde/', core_views.management_sde, name='management_sde'),
    path('management/system/', core_views.management_celery, name='management_celery'), # New Route

    # --- Public Area ---
    path('', core_views.landing_page, name='landing_page'),
    path('profile/', core_views.profile_view, name='profile'),
    
    # Character Switching Routes
    path('profile/switch/<int:char_id>/', core_views.switch_character, name='switch_character'),
    path('profile/make_main/<int:char_id>/', core_views.make_main, name='make_main'),
    
    # API Routes
    path('api/refresh_profile/<int:char_id>/', core_views.api_refresh_profile, name='api_refresh_profile'),

    # ESI Auth Routes
    path('', include('esi_auth.urls')),
]