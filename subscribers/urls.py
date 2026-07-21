from django.urls import path

from . import views

app_name = 'subscribers'

urlpatterns = [
    path('inscription/', views.subscribe, name='subscribe'),
    path('confirmation/<str:token>/', views.confirm, name='confirm'),
    path('desinscription/<uuid:token>/', views.unsubscribe, name='unsubscribe'),
    path('importer/', views.subscriber_import, name='import'),
    path('exporter/', views.subscriber_export, name='export'),
    path('ajouter/', views.subscriber_edit, name='create'),
    path('actions/segment/', views.subscriber_bulk_segment, name='bulk_segment'),
    path('segments/', views.segment_list, name='segment_list'),
    path('segments/nouveau/', views.segment_edit, name='segment_create'),
    path('segments/<int:pk>/', views.segment_detail, name='segment_detail'),
    path('segments/<int:pk>/modifier/', views.segment_edit, name='segment_edit'),
    path('segments/<int:pk>/supprimer/', views.segment_delete, name='segment_delete'),
    path('<int:pk>/', views.subscriber_detail, name='detail'),
    path('<int:pk>/modifier/', views.subscriber_edit, name='edit'),
    path('<int:pk>/anonymiser/', views.subscriber_anonymize, name='anonymize'),
    path('', views.subscriber_list, name='list'),
]