from django.urls import path
from . import views

urlpatterns = [
    # DOCTRINES (Public)
    path('doctrines/', views.doctrine_list, name='doctrine_list'),
    path('doctrines/api/<int:fit_id>/', views.doctrine_detail_api, name='doctrine_detail_api'),

    # DOCTRINES (Management)
    path('management/doctrines/', views.manage_doctrines, name='manage_doctrines'),
]