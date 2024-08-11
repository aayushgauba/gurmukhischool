from django.contrib import admin
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('students/<int:course_id>', views.students, name='students'),
    path('', views.courses, name='courses'),
    path('courses/add', views.courseAdd, name='courseAdd'),
    path('courses/<int:course_id>', views.course, name='course'),
    path('section/<int:course_id>/add', views.sectionAdd, name='sectionAdd'),
    path('section/<int:section_id>/folder/view/<int:folder_id>', views.folder, name='folder'),
    path('section/<int:section_id>/folder/file/upload/<int:folder_id>', views.uploadFile, name='uploadFile'),
    path('section/<int:section_id>/folder/add', views.folderAdd, name='folderAdd'),
    path('section/<int:section_id>/order/up', views.moveSectionUp, name = "moveSectionUp"),
    path('section/<int:section_id>/order/down', views.moveSectionDown, name = "moveSectionDown"),
    path('section/<int:section_id>/visibility', views.changeVisibility, name = "changeVisibility"),
    path('section/<int:section_id>/folder/assignment/create/<int:folder_id>', views.createAssignment, name='createAssignment'),
    path('section/<int:section_id>/folder/assignment/view/<int:folder_id>/<int:assignment_id>', views.viewAssignment, name='viewAssignment'),
    path('section/<int:section_id>/folder/assignment/edit/<int:folder_id>/<int:assignment_id>', views.editAssignment, name='editAssignment'),
    path('section/<int:section_id>/folder/assignment/edit/<int:folder_id>/<int:assignment_id>', views.editAssignment, name='editAssignment'),
    path('submission/<int:user_id>/folder/<folder_id>/assignment/<int:assignment_id>', views.submissions, name='submissions'),
    path('section/<int:section_id>/folder/assignment/delete/<int:folder_id>/<int:assignment_id>', views.deleteAssignment, name='deleteAssignment'),
    path('section/<int:section_id>/folder/assignment/delete/<int:folder_id>/<int:assignment_id>', views.deleteAssignment, name='deleteAssignment'),
    path('section/<int:section_id>/folder/assignment/submit/<int:folder_id>/<int:assignment_id>/delete', views.deleteSubmission, name='deleteSubmission'),
    path('section/<int:section_id>/folder/assignment/upload/<int:folder_id>/<int:assignment_id>/existing', views.addExistingFilesToAssignment, name='addExistingFilesToAssignment'),
    path('section/<int:section_id>/folder/assignment/delete/<int:folder_id>/<int:assignment_id>', views.deleteFilesFromAssignment, name='deleteFilesFromAssignment'),
    path('section/<int:section_id>/folder/assignment/upload/<int:folder_id>/<int:assignment_id>/new', views.addNewFilesToAssignment, name='addNewFilesToAssignment'),
    path('section/<int:section_id>/folder/assignment/submit/<int:folder_id>/<int:assignment_id>', views.submitFilesToAssignment, name='submitFilesToAssignment'),
    path('file/<int:file_id>', views.fileView, name = "fileView"),
    path('file/delete/<int:pk>/<int:section_id>/<int:folder_id>', views.delete_file, name='delete_file'),
    path('login', views.login, name='login'),
    path('students/add/<int:course_id>', views.addStudents, name='addStudents'),
    path('registration', views.registration, name='registration'),
    path('student', views.stuMode, name = 'student')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)