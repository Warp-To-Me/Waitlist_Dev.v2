from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('auth/', include('esi_auth.urls', namespace='esi_auth')),

    # Waitlist Application Data
    path('waitlist/', include('waitlist_data.urls', namespace='waitlist_data')),

    # Core Application (Landing, Profile, Management, SRP)
    # This captures the root URL, so it's placed last.
    path('', include('core.urls', namespace='core')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)