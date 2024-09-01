from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('events', views.events, name='events'),
    path('about', views.about, name='about'),
    path('contact', views.contact, name='contact'),
    path('sitemap', views.sitemap, name='sitemap'),
]
