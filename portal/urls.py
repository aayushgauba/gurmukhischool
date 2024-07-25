from django.contrib import admin
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.courses, name='courses'),
    path('courses/add', views.courseAdd, name='courseAdd'),
    path('courses/<int:course_id>', views.course, name='course'),
    path('section/<int:course_id>/add', views.sectionAdd, name='sectionAdd'),
    path('section/<int:section_id>/folder/view/<int:folder_id>', views.folder, name='folder'),
    path('section/<int:section_id>/folder/upload/<int:folder_id>', views.uploadFile, name='uploadFile'),
    path('section/<int:section_id>/folder/add', views.folderAdd, name='folderAdd'),
    path('section/<int:section_id>/order/up', views.moveSectionUp, name = "moveSectionUp"),
    path('section/<int:section_id>/order/down', views.moveSectionDown, name = "moveSectionDown"),
    path('section/<int:section_id>/visibility', views.changeVisibility, name = "changeVisibility"),
    path('login', views.login, name='login'),
    path('registration', views.registration, name='registration'),
    path('student', views.stuMode, name = 'student')
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)