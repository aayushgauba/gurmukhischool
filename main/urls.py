from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.indexMain, name='indexMain'),
    # path('events', views.eventsMain, name='eventsMain'),
    path('about', views.aboutMain, name='aboutMain'),
    path('contact', views.contact, name='contact'),
    path('sitemap', views.sitemap, name='sitemap'),
    path('subscribe', views.subscribe, name='subscribe'),
    path('subscribe/submit', views.subscribePOST, name='subscribePOST'),
]