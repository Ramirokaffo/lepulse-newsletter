from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('tableau-de-bord/', views.dashboard, name='dashboard'),
    path('statistiques/', views.statistics, name='statistics'),
    path('journal-audit/', views.audit_log, name='audit_log'),
]