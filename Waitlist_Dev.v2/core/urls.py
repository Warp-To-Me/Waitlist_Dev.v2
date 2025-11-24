from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # Custom Management (Core)
    path('management/', core_views.custom_admin_dashboard, name='custom_admin'),
    
    # Public
    path('', core_views.landing_page, name='landing_page'),
    
    # Include ESI Auth URLs
    path('auth/', include('esi_auth.urls')),
]