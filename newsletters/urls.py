from django.urls import path

from . import views

app_name = 'newsletters'

urlpatterns = [
    path('', views.archive, name='archive'),
    path('lire/<slug:slug>/', views.detail, name='detail'),
    path('suivi/ouverture/<uuid:token>.gif', views.track_open, name='track_open'),
    path('suivi/clic/<uuid:token>/', views.track_click, name='track_click'),
    path('gestion/', views.newsletter_list, name='list'),
    path('gestion/nouvelle/', views.newsletter_edit, name='create'),
    path('gestion/<int:pk>/modifier/', views.newsletter_edit, name='edit'),
    path('campagnes/', views.campaign_list, name='campaign_list'),
    path('campagnes/nouvelle/', views.campaign_create, name='campaign_create'),
    path('campagnes/<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('campagnes/<int:pk>/apercu/', views.campaign_preview, name='campaign_preview'),
    path('campagnes/<int:pk>/test/', views.campaign_test, name='campaign_test'),
    path('campagnes/<int:pk>/planifier/', views.campaign_schedule, name='campaign_schedule'),
    path('campagnes/<int:pk>/annuler/', views.campaign_cancel, name='campaign_cancel'),
    path('campagnes/<int:pk>/exporter/', views.campaign_export, name='campaign_export'),
    path('campagnes/<int:pk>/envoyer/', views.campaign_send, name='campaign_send'),
]