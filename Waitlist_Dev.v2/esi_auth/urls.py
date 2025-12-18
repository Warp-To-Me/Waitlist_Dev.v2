from django.urls import path
from . import views

urlpatterns = [
    path('auth/sso/login/', views.sso_login, name='sso_login'),
    path('auth/login-options/', views.auth_login_options, name='auth_login_options'),
    path('auth/add_alt/', views.add_alt, name='add_alt'),
    path('auth/srp/', views.srp_auth, name='srp_auth'), # New Route
    path('sso/callback/', views.sso_callback, name='sso_callback'),
    path('auth/logout/', views.logout_view, name='logout'),
]