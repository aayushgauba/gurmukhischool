from django.contrib import admin
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('students/<int:course_id>', views.students, name='students'),
    path('students/remove/<int:course_id>', views.removeStudentFromCourse, name='removeStudentFromCourse'),
    path('', views.courses, name='courses'),
    path('admin/', views.adminViewHome, name = 'adminViewHome'),
    path('admit/user/waitlist', views.admit_user, name='admit_user'),
    path('admin/carousel', views.carousel_management, name = 'carousel_management'),
    path('admin/users', views.adminUsers, name = 'adminUsers'),
    path('admin/contact', views.adminContactView, name = 'adminContactView'),
    path('courses/syllabus/add/<int:course_id>', views.upload_syllabus, name = 'upload_syllabus'),
    path('courses/syllabus/view/<int:course_id>', views.view_syllabus, name = 'view_syllabus'),
    path('courses/add', views.courseAdd, name='courseAdd'),
    path('courses/<int:course_id>', views.course, name='course'),
    path('section/<int:course_id>/add', views.sectionAdd, name='sectionAdd'),
    path('section/<int:section_id>/folder/view/<int:folder_id>', views.folder, name='folder'),
    path('section/<int:section_id>/folder/file/upload/<int:folder_id>', views.uploadFile, name='uploadFile'),
    path('folder/add', views.folderAdd, name='folderAdd'),
    path('section/<int:section_id>/order/up', views.moveSectionUp, name = "moveSectionUp"),
    path('section/<int:section_id>/order/down', views.moveSectionDown, name = "moveSectionDown"),
    path('section/<int:section_id>/visibility', views.changeVisibility, name = "changeVisibility"),
    path('section/<int:section_id>/folder/assignment/create/<int:folder_id>', views.createAssignment, name='createAssignment'),
    path('section/<int:section_id>/folder/assignment/view/<int:folder_id>/<int:assignment_id>', views.viewAssignment, name='viewAssignment'),
    path('section/<int:section_id>/folder/assignment/edit/<int:folder_id>/<int:assignment_id>', views.editAssignment, name='editAssignment'),
    path('section/<int:section_id>/folder/assignment/edit/<int:folder_id>/<int:assignment_id>', views.editAssignment, name='editAssignment'),
    path('submission/<int:folder_id>/folder/<int:user_id>/assignment/<int:assignment_id>', views.submissions, name='submissions'),
    path('grade/submission/<int:folder_id>/folder/<int:user_id>/assignment/<int:assignment_id>/<int:course_id>', views.assignGradeToAssignment, name='assignGradeToAssignment'),
    path('section/<int:section_id>/folder/assignment/delete/<int:folder_id>/<int:assignment_id>', views.deleteAssignment, name='deleteAssignment'),
    path('section/<int:section_id>/folder/assignment/delete/<int:folder_id>/<int:assignment_id>', views.deleteAssignment, name='deleteAssignment'),
    path('section/<int:section_id>/folder/assignment/submit/<int:folder_id>/<int:assignment_id>/delete', views.deleteSubmission, name='deleteSubmission'),
    path('section/<int:section_id>/folder/assignment/upload/<int:folder_id>/<int:assignment_id>/existing', views.addExistingFilesToAssignment, name='addExistingFilesToAssignment'),
    path('section/<int:section_id>/folder/assignment/delete/<int:folder_id>/<int:assignment_id>', views.deleteFilesFromAssignment, name='deleteFilesFromAssignment'),
    path('section/<int:section_id>/folder/assignment/upload/<int:folder_id>/<int:assignment_id>/new', views.addNewFilesToAssignment, name='addNewFilesToAssignment'),
    path('reset', views.PasswordResetView, name='reset'),
    path('section/<int:section_id>/folder/assignment/submit/<int:folder_id>/<int:assignment_id>', views.submitFilesToAssignment, name='submitFilesToAssignment'),
    path('grade/view/<int:folder_id>/folder/assignment/<int:assignment_id>', views.gradesforAssignment, name='gradesforAssignment'),
    path('file/<int:file_id>', views.fileView, name = "fileView"),
    path('file/delete/<int:pk>/<int:section_id>/<int:folder_id>', views.delete_file, name='delete_file'),
    path('login', views.login, name='login'),
    path('grades/<int:course_id>', views.grades, name='grades'),
    path('students/add/<int:course_id>', views.addStudents, name='addStudents'),
    path('registration', views.registration, name='registration'),
    path('reset/<uidb64>/<token>/', views.reset, name='resetEmail'),
    path('student', views.stuMode, name = 'student'),
    path('announcements', views.announcements, name = 'announcements'),
    path('announcement/create', views.create_announcement, name='create_announcement'),
    path('attendance/<int:course_id>', views.attendance, name='attendance'),
    path('attendance/<int:course_id>/<int:year>/<int:month>/', views.attendance, name='attendance'),
    path('attendance/mark/<int:course_id>/<int:day>/<int:month>/<int:year>/', views.mark_attendance, name='mark_attendance'),
    path('profile/<int:course_id>', views.profile, name='profile'),
    path('profile', views.profile, name='profile'),
    path('profile/upload/photo/<int:course_id>', views.upload_profile_photo, name='upload_profile_photo_with_course'),
    path('profile/upload/photo', views.upload_profile_photo, name='upload_profile_photo'),
    path('carousel/photo/up/<int:image_id>', views.moveCarouselImageUp, name = "moveCarouselImageUp"),
    path('carousel/photo/down/<int:image_id>', views.moveCarouselImageDown, name = "moveCarouselImageDown"),
    path('delete_carousel_image/', views.delete_carousel_image, name='delete_carousel_image'),
    path('logout/', views.signout, name='logout'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)