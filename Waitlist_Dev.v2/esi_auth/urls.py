from django.urls import path
from . import views

urlpatterns = [
    path('auth/login/', views.sso_login, name='sso_login'),
    path('auth/add_alt/', views.add_alt, name='add_alt'),
    path('auth/srp/', views.srp_auth, name='srp_auth'), # New Route
    path('sso/callback/', views.sso_callback, name='sso_callback'),
    path('auth/logout/', views.logout_view, name='logout'),
]