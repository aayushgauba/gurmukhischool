from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login', views.login, name='login'),
    path('events', views.events, name='events'),
    path('registration', views.registration, name='registration'),
    path('about', views.about, name='about'),
    path('contact', views.contact, name='contact'),
]
