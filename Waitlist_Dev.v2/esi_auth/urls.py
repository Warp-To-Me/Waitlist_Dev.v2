from django.urls import path
from . import views

app_name = 'esi_auth'

urlpatterns = [
    path('login/', views.login, name='sso_login'),
    path('callback/', views.sso_callback, name='callback'),
    path('logout/', views.logout, name='logout'),
]