from django.shortcuts import render, redirect
from portal.models import CustomUser, Schedule, WeeklyEmail, Courses, Section, Folder, Grade, Announcement, Attendance, CarouselImage
from django.contrib.auth.hashers import make_password, check_password
from django.http import HttpRequest, JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from main.models import BlacklistedIP
from django.http import HttpResponse
from django.contrib.auth.tokens import default_token_generator
from .forms import UploadedFileForm, FileUploadForm, AnnouncementForm,UploadedAttendanceForm,GroupPhotoUploadForm, ProfilePhotoForm, CarouselImageForm, SyllabusUploadForm
from .models import UploadedFile, Assignment, filestoAssignment
from main.models import CarouselImage as Carousel
from main.forms import CarouselImageForm as MainCarouselImageForm
from django.contrib.auth.decorators import login_required
from .decorators import superuser_required, teacher_required, admin_required, approved_required, emailSender_required
from django.views.decorators.http import require_POST
from asgiref.sync import sync_to_async
from pages.models import Contact
from django.core.exceptions import ValidationError
import re
import os
import asyncio
import threading
import calendar
from datetime import datetime
import json

@approved_required
@login_required
def course(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user = request.user
    course = Courses.objects.get(id = course_id)
    if request.user.usertype == 'Teacher':
        sections = Section.objects.filter(Course_id = course.id).order_by("ONum")
    elif request.user.usertype == 'Student':
        if course.People.filter(id = request.user.id).exists():
            sections = Section.objects.filter(Course_id = course.id).order_by("ONum")
        else:
            return redirect("courses")
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_course.html", {"course":course,"profile_photo":profile_photo, "user":user, "sections":sections})
    else:   
        return render(request, "portal/desktop_course.html", {"course":course,"profile_photo":profile_photo, "user":user, "sections":sections})

@approved_required
@teacher_required
@superuser_required
@login_required
def students(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = Courses.objects.get(id = course_id)
    students = course.People.all()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_students.html", {"students":students,"profile_photo":profile_photo, "course":course})
    else:
        return render(request, "portal/desktop_students.html", {"students":students, "profile_photo":profile_photo, "course":course})

@approved_required
@login_required
def fileView(request, file_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    file = UploadedFile.objects.get(id = file_id)
    context = {
        'file': file,
        'file_type': file.file.url.split('.')[-1].lower(),
        "profile_photo":profile_photo,
    }
    return render(request, 'portal/fileDetail.html', context)

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def delete_file(request, pk, section_id, folder_id):
    file = UploadedFile.objects.get(pk=pk)
    if request.method == 'POST':
        if file.file.path and os.path.exists(file.file.path):
            os.remove(file.file.path)
            file.delete()
        elif file.file.path and not os.path.exists(file.file.path):
            file.delete()
        return redirect('folder', section_id, folder_id)

@approved_required
@teacher_required
@superuser_required
@login_required
def addExistingFilesToAssignment(request, section_id, folder_id, assignment_id):
    if request.method == "POST":
        file_id = request.POST.get('existing_file')
        file = UploadedFile.objects.get(id = file_id)
        assignment = Assignment.objects.get(id = assignment_id)
        assignment.files.add(file)
        return redirect("viewAssignment", section_id,folder_id, assignment_id)

@login_required
@approved_required
@admin_required
def carousel_management(request: HttpRequest):
    images = CarouselImage.objects.all()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    mainImages = Carousel.objects.all()
    images = images.order_by("order")
    mainImages = mainImages.order_by("order")
    form = CarouselImageForm()
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    mainform = MainCarouselImageForm()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_adminCarousel.html", {'profile_photo':profile_photo, 'images': images,'mainImages':mainImages, 'form': form, 'mainform':mainform})
    else:   
        return render(request, "portal/desktop_adminCarousel.html", {'profile_photo':profile_photo, 'images': images,'mainImages':mainImages, 'form': form, 'mainform':mainform})

@login_required
@approved_required
@admin_required
@require_POST
def mainCarouselImageUpload(request):
    images = Carousel.objects.all()
    if images:
        count = images.count()
    else:
        count = 0
    form = MainCarouselImageForm(request.POST, request.FILES)
    if form.is_valid():
        image = form.save()
        image.order = count
        image.save() 
        return redirect('carousel_management')

@login_required
@approved_required
@admin_required
@require_POST
def gurmukhiSchoolImageUpload(request):
    images = CarouselImage.objects.all()
    if images:
        count = images.count()
    else:
        count = 0
    form = CarouselImageForm(request.POST, request.FILES)
    if form.is_valid():
        image = form.save()
        image.order = count
        image.save() 
        return redirect('carousel_management')

@login_required
@approved_required
@admin_required
def moveMainCarouselImageUp(request, image_id):
    image = Carousel.objects.get(id = image_id)
    order = image.order
    if order >0:
        newImage = Carousel.objects.get(order = (order-1))
        image.order = order -1
        newImage.order = order
        image.save()
        newImage.save()
    return redirect("carousel_management")

@login_required
@approved_required
@admin_required
def moveMainCarouselImageDown(request, image_id):
    image = Carousel.objects.get(id = image_id)
    order = image.order
    print(Carousel.objects.get(order = (order +1)))
    if order < Carousel.objects.all().count():
        newImage = Carousel.objects.get(order = (order+1))
        image.order = order +1
        newImage.order = order
        image.save()
        newImage.save()
    return redirect("carousel_management")

@login_required
@approved_required
@admin_required
def moveCarouselImageUp(request, image_id):
    image = CarouselImage.objects.get(id = image_id)
    order = image.order
    if order >0:
        newImage = CarouselImage.objects.get(order = (order-1))
        image.order = order -1
        newImage.order = order
        image.save()
        newImage.save()
    return redirect("carousel_management")

@login_required
@approved_required
@admin_required
def moveCarouselImageDown(request, image_id):
    image = CarouselImage.objects.get(id = image_id)
    order = image.order
    print(CarouselImage.objects.get(order = (order +1)))
    if order < CarouselImage.objects.all().count():
        newImage = CarouselImage.objects.get(order = (order+1))
        image.order = order +1
        newImage.order = order
        image.save()
        newImage.save()
    
    return redirect("carousel_management")

@require_POST
@login_required
@approved_required
@admin_required
def contactSpam(request, contact_id):
    try:
        contact = Contact.objects.get(id=contact_id)
        contact.is_spam = True
        contact.save()
        return redirect("contact")
    except Contact.DoesNotExist:
        return redirect("contact")
    
@require_POST
@login_required
@approved_required
@admin_required
def contactDelete(request, contact_id):
    try:
        contact = Contact.objects.get(id=contact_id)
        contact.delete()
        return redirect("contact")
    except Contact.DoesNotExist:
        return redirect("contact")

@require_POST
@login_required
@approved_required
@admin_required
def delete_carousel_image(request):
    if request.method == 'POST':
        image_id = request.POST.get('image_id')
        image =  CarouselImage.objects.get(id=image_id)
        if image.image.path and os.path.exists(image.image.path):
            os.remove(image.image.path)
        image.delete()
        return redirect('carousel_management')
    
@require_POST
@login_required
@approved_required
@admin_required
def delete_main_carousel_image(request):
    if request.method == 'POST':
        image_id = request.POST.get('main_image_id')
        image =  Carousel.objects.get(id=image_id)
        if image.image.path and os.path.exists(image.image.path):
            os.remove(image.image.path)
        image.delete()
        return redirect('carousel_management')

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def addNewFilesToAssignment(request, section_id, folder_id, assignment_id):
    if request.method == "POST":
        form = UploadedFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.save()
            assignment = Assignment.objects.get(id = assignment_id)
            assignment.files.add(file)
            return redirect("viewAssignment", section_id,folder_id, assignment_id)
    else:
        form = UploadedFileForm()

@approved_required
@require_POST
@login_required
def submitFilesToAssignment(request, section_id, folder_id, assignment_id):
    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES, user_id = request.user.id, assignment_id = assignment_id)
        if form.is_valid():
            form.save()
            return redirect("viewAssignment", section_id, folder_id, assignment_id)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def deleteFilesFromAssignment(request, section_id, folder_id, assignment_id):
    if request.method == "POST":
        file_id = request.POST.get('file_id')
        assignment = Assignment.objects.get(id = assignment_id)
        file = UploadedFile.objects.get(id = file_id)
        assignment.files.remove(file)
        if not file.folder_id:
            if file.file.path and os.path.exists(file.file.path):
                os.remove(file.file.path)
                file.delete()
            elif file.file.path and not os.path.exists(file.file.path):
                file.delete()
        return redirect("viewAssignment", section_id, folder_id, assignment_id)

@approved_required
@login_required
def viewAssignment(request: HttpRequest, section_id, folder_id, assignment_id):
    assignment = Assignment.objects.get(id = assignment_id)
    files = UploadedFile.objects.all()
    form = UploadedFileForm()
    folder = Folder.objects.get(id = folder_id)
    course = Courses.objects.get(id = folder.Course_id)
    context = {}
    studentform = FileUploadForm(user_id = request.user.id, assignment_id = assignment_id)
    if request.user.usertype == "Student":
        submissions = filestoAssignment.objects.filter(user_id = request.user.id, assignment_id = assignment_id)
        context = {"submissions":submissions,"course":course, "assignment":assignment, "folder":folder,"form":form, "studentform":studentform, "files":files, "section_id":section_id, "folder_id":folder_id}
    elif request.user.is_superuser and request.user.usertype == "Teacher":
        submissions = filestoAssignment.objects.filter(assignment_id = assignment_id).distinct()
        users = CustomUser.objects.filter(id__in=filestoAssignment.objects.filter(assignment_id=assignment.id).values('user_id').distinct())
        context = {"submissions":submissions, "assignment":assignment, "course":course, "users":users, "folder":folder, "form":form, "studentform":studentform, "files":files, "section_id":section_id, "folder_id":folder_id}
    files = files.exclude(id__in = assignment.files.values_list('id', flat=True))
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_assignmentDetail.html", context = context)
    else:
        return render(request, "portal/desktop_assignmentDetail.html", context = context)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def createAssignment(request, section_id, folder_id):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        due_date = request.POST.get('due_date')
        assignment = Assignment.objects.create(title = title, description = description, due_date = due_date)
        folder = Folder.objects.get(id = folder_id)
        folder.Assignments.add(assignment)
        return redirect('folder', section_id, folder_id)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def editAssignment(request, section_id, folder_id, assignment_id):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        due_date = request.POST.get('due_date')
        assignment = Assignment.objects.get(id = assignment_id)
        assignment.title = title
        assignment.description = description
        if due_date != "":
            assignment.due_date = due_date
        assignment.save()
        return redirect('viewAssignment', section_id, folder_id, assignment_id)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def deleteAssignment(request, section_id, folder_id, assignment_id):
    if request.method == 'POST':
        assignment = Assignment.objects.get(id = assignment_id)
        assignment.delete()
        return redirect('folder',section_id, folder_id)

@approved_required
@require_POST
@login_required
def deleteSubmission(request, section_id, folder_id, assignment_id):
    if request.method == 'POST':
        submission_id = request.POST.get('submission_id')
        submission = filestoAssignment.objects.get(id = submission_id)
        if submission.file.path and os.path.exists(submission.file.path):
            os.remove(submission.file.path)
            submission.delete()
        return redirect('viewAssignment', section_id, folder_id, assignment_id)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def uploadFile(request, section_id, folder_id):
    if request.method == 'POST':
        form = UploadedFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save()
            folder = Folder.objects.get(id = folder_id)
            folder.Files.add(uploaded_file)
            return redirect('folder', section_id, folder_id)
    else:
        form = UploadedFileForm()

@approved_required
@login_required
def folder(request: HttpRequest, section_id, folder_id):
    user = request.user
    form = UploadedFileForm()
    folder = Folder.objects.get(id = folder_id)
    course = Courses.objects.get(id = folder.Course_id)
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_folderView.html", {"course":course, "user":user, "form":form, "folder":folder, "section_id":section_id})
    else:
        return render(request, "portal/desktop_folderView.html", {"course":course, "user":user, "form":form, "folder":folder, "section_id":section_id})

@approved_required
@teacher_required
@superuser_required
@login_required
def moveSectionUp(request, section_id):
    section = Section.objects.get(id = section_id)
    course_id = section.Course_id
    if section.ONum >0:
        section_new = Section.objects.get(ONum = int(section.ONum - 1), Course_id = section.Course_id)
        section.ONum = section.ONum -1
        section.save()
        section_new.ONum = section_new.ONum + 1
        section_new.save()
    return redirect("course", course_id)

@approved_required
@teacher_required
@superuser_required
@login_required
def moveSectionDown(request, section_id):
    section = Section.objects.get(id = section_id)
    count = Section.objects.filter(Course_id = section.Course_id).count()
    if count is None:
        count = 0
    course_id = section.Course_id
    if section.ONum<count and count >1:
        section_new = Section.objects.get(ONum = int(section.ONum + 1), Course_id = section.Course_id)
        section.ONum = section.ONum +1
        section.save()
        section_new.ONum = section_new.ONum - 1
        section_new.save()
    return redirect("course", course_id)

@approved_required
@teacher_required
@superuser_required
@login_required
def changeVisibility(request, section_id):
    section = Section.objects.get(id = section_id)
    if section.Status == True:
        section.Status = False
    else:
        section.Status = True
    section.save()
    course_id = section.Course_id
    return redirect("course", course_id)

def view_syllabus(request, course_id):
    course = Courses.objects.get(id=course_id)
    if course.Syllabus:
        response = HttpResponse(course.Syllabus, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename=' + course.Syllabus.name
        return response
    else:
        return HttpResponse("No syllabus available.", content_type='text/plain')
    
def viewMobileContentUpload(request, file_id):
    file = UploadedFile.objects.get(id = file_id)
    response = HttpResponse(file.file, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename=' + str(file.id)
    return response

@approved_required
@login_required
def courses(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user = request.user
    form = SyllabusUploadForm()
    courses = None
    if user.usertype == "Teacher":
        courses = Courses.objects.all().order_by("id")
    elif user.usertype == "Student":
        courses = Courses.objects.filter(People = request.user).order_by("id")
    elif user.usertype == "Admin" and user.is_superuser:
        return redirect("adminViewHome")
    elif user.usertype == "EmailSender" and user.is_superuser:
        return redirect("calenderNotification")
    else:
        return render(request, "portal/unknown_usertype.html", {"user": user})
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if "mobile" in user_agent:
        return render(request, 'portal/mobile_courses.html', {"user": user,"profile_photo":profile_photo, "courses": courses, "form": form})
    else:
        return render(request, "portal/desktop_courses.html", {"user": user, "profile_photo":profile_photo, "courses": courses, "form": form})



@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def assignGradeToAssignment(request, folder_id, user_id, assignment_id, course_id):
    try:
        grade = Grade.objects.get(user_id=user_id, assignment_id=assignment_id, course_id = course_id)
        newGrade = request.POST.get("grade")
        grade.grade = newGrade
        grade.save()
    except Grade.DoesNotExist:
        newGrade = request.POST.get("grade")
        Grade.objects.create(user_id=user_id, assignment_id=assignment_id, grade=newGrade, course_id= course_id)
    except Exception as e:
        print(f"An error occurred: {e}")
    return redirect("submissions", folder_id, user_id, assignment_id)

@approved_required
@login_required
def grades(request: HttpRequest, course_id = None):
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    if course_id is not None:
        grades = Grade.objects.filter(course_id = course_id)
        if grades:
            if request.user.usertype == "Student":
                grades = Grade.objects.filter(user_id = request.user.id, course_id = course_id)
                gradeArray = []
                final = 0
                print(grades.count())
                for grade in grades:
                    dict = {"title":Assignment.objects.get(id = grade.assignment_id).title, "grade":grade.grade}
                    gradeArray.append(dict)
                    final = final + grade.grade
                finals = final/grades.count()
                course = Courses.objects.get(id = course_id)
                if "mobile" in user_agent:
                    return render(request, "portal/mobile_grades.html", {"grades":gradeArray, "course":course, "final":finals})
                else:
                    return render(request, "portal/desktop_grades.html", {"grades":gradeArray, "course":course, "final":finals, "profile_photo":profile_photo})
            elif request.user.is_superuser and request.user.usertype == "Teacher":
                grades = Grade.objects.filter(course_id = course_id)
                sections = Section.objects.filter(Course_id=course_id)
                folders = Folder.objects.filter(section__in=sections.values_list('id', flat=True))
                assignments = Assignment.objects.filter(folder__in=folders.values_list('id', flat=True)).distinct()        
                gradeArray = []
                final = 0
                print(grades.count())
                for assignment in assignments:
                    grades = Grade.objects.filter(assignment_id = assignment.id)
                    average = 0
                    for grade in grades:
                        average = average + grade.grade
                    average = average / grades.count()
                    dict = {"title":Assignment.objects.get(id = grade.assignment_id).title, "grade":average}
                    gradeArray.append(dict)
                    final = final + average
                finals = final/assignments.count()
                course = Courses.objects.get(id = course_id)
                if "mobile" in user_agent:
                    return render(request, "portal/mobile_grades.html", {"grades":gradeArray, "course":course, "final":finals})
                else:
                    return render(request, "portal/desktop_grades.html", {"grades":gradeArray, "course":course, "final":finals, "profile_photo":profile_photo})
        else:
            course = Courses.objects.get(id = course_id)
            if "mobile" in user_agent:
                return render(request, "portal/mobile_grades.html", {"course":course})
            else:
                return render(request, "portal/desktop_grades.html", {"course":course})
        return HttpResponse(grades = Grade.objects.filter(user_id = request.user.id, course_id = course_id))
    else:
        if request.user.is_superuser and request.user.usertype == "Teacher":
            courses = Courses.objects.all()
            averageArray = []
            for course in courses:
                grades = Grade.objects.filter(course_id = course.id)
                if grades:
                    averageGrade = float(0)
                    for grade in grades:
                        averageGrade += grade
                    averageGrade = float(averageGrade / float(len(grades)))
                    dict = {'id':course_id, 'grade':averageGrade}
                else:
                    dict = {'id':course_id, 'grade':None}
                averageArray.append(dict)
                if "mobile" in user_agent:
                    return render(request, "portal/mobile_grades.html", {'grades':averageArray})
                else:
                    return render(request, "portal/desktop_grades.html", {'grades':averageArray})

@approved_required
def announcements(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if request.user.usertype == "Teacher" and request.user.is_superuser:
        announcements = Announcement.objects.all()
    elif request.user.usertype == "Student" and not request.user.is_superuser:
        student = CustomUser.objects.get(id=request.user.id)
        courses = Courses.objects.filter(People=student)
        announcements = Announcement.objects.filter(recipients__in=courses)
    else:
        announcements = Announcement.objects.none()  # Handle other user types if necessary
    if "mobile" in user_agent:
        return render(request, "portal/mobile_announcements.html", {"announcements": announcements})
    else:
        return render(request, "portal/desktop_announcements.html", {"announcements": announcements, "profile_photo":profile_photo})

@approved_required
@teacher_required
@superuser_required
@login_required
def mark_attendance(request: HttpRequest, course_id, day, month, year):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    if request.method == 'POST':
        selected_day = request.POST.get('day')
        selected_month = request.POST.get('month')
        selected_year = request.POST.get('year')

        students = Courses.objects.get(id=course_id).People.all()

        for student in students:
            status = 'Absent'  # Default to absent
            if f'attendance_status_{student.id}' in request.POST:
                status = 'Present'

            # Update or create the attendance record
            Attendance.objects.update_or_create(
                student=student,
                day=selected_day,
                month=selected_month,
                year=selected_year,
                defaults={'status': status}
            )

        return redirect('attendance', course_id=course_id)
    else:
        all_students = Courses.objects.get(id=course_id).People.all()
        course = Courses.objects.get(id=course_id)

        # Query attendance records for the given day, month, and year
        attendance_records = Attendance.objects.filter(
            day=day, month=month, year=year
        )

        attendanceArray =[]
        # Create a dictionary to easily check if a student was present or absent
        for record in attendance_records:
            if record.status == "Present":
                attendanceArray.append(record.student_id)
        context = {
            'course': course,
            'all_students': all_students,
            'day': day,
            'month': month,
            'year': year,
            'attendance_dict': attendanceArray,
            "profile_photo":profile_photo,
        }
        user_agent = request.META['HTTP_USER_AGENT'].lower()
        if "mobile" in user_agent:
            return render(request, 'portal/mobile_attendanceAdd.html', context)
        else:
            return render(request, 'portal/desktop_attendanceAdd.html', context)

@approved_required
@login_required
def attendance(request: HttpRequest, course_id, year=None, month=None):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    course = Courses.objects.get(id = course_id)
    if not year or not month:
        year = datetime.now().year
        month = datetime.now().month
    cal = calendar.Calendar()
    month_days = list(cal.itermonthdays2(year, month))
    today = datetime.now().day if year == datetime.now().year and month == datetime.now().month else None
    prev_month = month - 1
    next_month = month + 1
    prev_year = year
    next_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    if next_month == 13:
        next_month = 1
        next_year += 1

    weeks = []
    week = [None] * 7 

    for day, weekday in month_days:
        if day == 0:
            continue
        week[weekday] = day
        if weekday == 6:
            weeks.append(week)
            week = [None] * 7
    if any(week):
        weeks.append(week)

    if not request.user.is_superuser and request.user.usertype == "Student":
        attendance = Attendance.objects.filter(year = year, month = month, student = request.user, status = "Present").values_list('day', flat=True)
        attendance_days = list(attendance)
        absent = Attendance.objects.filter(year = year, month = month, student = request.user, status = "Absent").values_list('day', flat=True)
        absent_days = list(absent)
        context = {
        'year': year,
        'month': month,
        'month_days': month_days,
        'today': today,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'weeks': weeks,
        'course':course,
        'attendance':attendance_days,
        'absent':absent_days,
        'profile_photo':profile_photo,
    }
    else:
        photoform = GroupPhotoUploadForm()
        try:
            schedule = Schedule.objects.get(course = Courses.objects.get(id = course_id))
        except Exception as e:
            schedule = None
        attendanceForm = UploadedAttendanceForm()
        if schedule:
            startDate = datetime.strptime(schedule.startDate, "%Y-%m") 
            endDate = datetime.strptime(schedule.endDate, "%Y-%m") 
            currDate = datetime(year, month, 1)
            if startDate <= currDate and currDate <= endDate:
                allowed_days = json.loads(schedule.days)
                allowed_days = list(map(int, allowed_days))
            else:
                allowed_days = []
        else:
            allowed_days = []
        context = {
        'attendanceform':attendanceForm,
        'allowed_days': allowed_days,
        'photoform':photoform,
        'year': year,
        'month': month,
        'month_days': month_days,
        'today': today,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'weeks': weeks,
        'course':course,
        'profile_photo':profile_photo,
    }
    if "mobile" in user_agent:        
        return render(request, 'portal/mobile_attendance.html', context)
    else:
        return render(request, 'portal/desktop_attendance.html', context)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def uploadAttendanceData(request, course_id):
    next_url = request.META.get('HTTP_REFERER', '/')
    form = UploadedAttendanceForm(request.POST, request.FILES)
    print("Submitted data:", form)
    if form.is_valid():
        form.save()
    return redirect(next_url)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def uploadGroupPhoto(request):
    next_url = request.META.get('HTTP_REFERER', '/')
    form = GroupPhotoUploadForm(request.POST, request.FILES)
    print("Submitted data:", form)
    if form.is_valid():
        form.save()
    return redirect(next_url)

@approved_required    
@teacher_required
@require_POST
def scheduleDefine(request, course_id):
    next_url = request.META.get('HTTP_REFERER', '/')
    choices = request.POST.getlist('week')
    startDate = request.POST.get('startDate')
    endDate= request.POST.get('endDate')
    choices = json.dumps(choices)
    course = Courses.objects.get(id = course_id)
    print(choices)
    try:
        schedule = Schedule.objects.get(course = course)
        schedule.delete()
        Schedule.objects.create(startDate = startDate, endDate = endDate, days=choices, course = course)
    except Exception as e:
        Schedule.objects.create(startDate = startDate, endDate = endDate, days=choices, course = course)
    return redirect(next_url)



@login_required
@admin_required
@approved_required
def adminViewHome(request:HttpRequest):
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user_type = request.POST.get('user_type')
        user = CustomUser.objects.get(id=user_id)
        user.usertype = user_type
        if user.usertype == "Teacher" or "Admin":
            user.is_superuser = True
        elif user.usertype == "Student":
            user.is_superuser = False
        user.is_active = True
        user.approved = True
        user.save()
        current_site = get_current_site(request)
        plain_text_message = f"Hello {user.username}, your account has been approved."
        subject = 'Account approved'
        message = render_to_string('email/accountApproved.html', {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
            'protocol': 'https' if request.is_secure() else 'http',
        })
        send_mail(subject, plain_text_message, 'noreply@stlouisgurudwara.org', [user.email],  html_message=message)
        return redirect("adminViewHome")
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    users = CustomUser.objects.filter(approved = False)
    if "mobile" in user_agent:
        return render(request, 'portal/mobile_adminHome.html', {"users":users, 'profile_photo':profile_photo})
    else:   
        return render(request, "portal/desktop_adminHome.html", {"users":users, 'profile_photo':profile_photo})

@login_required
@admin_required
@approved_required
def adminUsers(request:HttpRequest):
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    users = CustomUser.objects.filter(approved = True)
    if "mobile" in user_agent:
        return render(request, 'portal/mobile_adminUsers.html', {"users":users, "profile_photo":profile_photo})
    else:   
        return render(request, "portal/desktop_adminUsers.html", {"users":users, "profile_photo":profile_photo})


@require_POST
@login_required
@admin_required
@approved_required
def delete_user(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = CustomUser.objects.get(id=user_id)
        user.delete()
        return redirect('adminUsers')

@require_POST
@login_required
@admin_required
@approved_required
def admit_user(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = CustomUser.objects.get(id=user_id)
        user.approved = False
        user.save()
        return redirect('adminViewHome')


@require_POST
@teacher_required
@login_required
@approved_required
def deleteCourse(request, course_id):
    if request.method == 'POST':
        course = Courses.objects.get(id = course_id)
        sections = Section.objects.filter(Course_id = course_id)
        for section in sections:
            section.delete()
        grades = Grade.objects.filter(course_id = course_id)
        for grade in grades:
            grade.delete()    
        course.delete()
        return redirect("courses")

@require_POST
@teacher_required
@login_required
@approved_required
def deleteSection(request, section_id):
    section = Section.objects.get(id=section_id)
    course_id = section.Course_id
    section_order_num = section.ONum
    section.delete()
    remaining_sections = Section.objects.filter(Course_id=course_id).order_by('ONum')
    for idx, sec in enumerate(remaining_sections):
        if sec.ONum > section_order_num:
            sec.ONum = sec.ONum - 1
            sec.save()
    return redirect("course", course_id)

@login_required
@admin_required
@approved_required
def adminContactView(request:HttpRequest):
    contacts = Contact.objects.filter(is_spam = False)
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    if "mobile" in user_agent:
        return render(request, 'portal/mobile_adminContact.html', {"contacts":contacts, "profile_photo":profile_photo})
    else:   
        return render(request, "portal/desktop_adminContact.html", {"contacts":contacts, "profile_photo":profile_photo})

@login_required
@approved_required
@require_POST
def upload_profile_photo(request, course_id=None):
    form = ProfilePhotoForm(request.POST, request.FILES)
    if form.is_valid():
        new_photo = form.save(commit=False)
        new_photo.save()
        user = request.user
        user.modified_profile_photo = True
        user.save()
        request.user.profile_photos.add(new_photo)
        if course_id:
            return redirect('profile', course_id=course_id)
        else:
            return redirect('profile')

@approved_required
@login_required
def signout(request):
    logout(request) 
    return redirect('login')

def profile(request: HttpRequest, course_id=None):
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if course_id:
        course = Courses.objects.get(id=course_id)
    else:
        course = None
    user = request.user
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    form = ProfilePhotoForm()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_profile.html", {'course': course, 'user': user, 'form': form, "profile_photo":profile_photo})
    else:
        return render(request, "portal/desktop_profile.html", {'course': course, 'user': user, 'form': form, "profile_photo":profile_photo})

def send_announcement_emails(announcement):
    recipients = set()
    for course in announcement.recipients.all():  # Convert QuerySet to list
        students = course.People.filter(usertype='student').distinct()
        for student in students:
            if student.email not in recipients:
                print(f"Sending email to: {student.email}")
                recipients.add(student.email)
                try:
                    send_mail(
                        subject=f'New Announcement: {announcement.title}',
                        message=announcement.content,
                        from_email='noreply@stlouisgurudwara.org',
                        recipient_list=[student.email],
                        fail_silently=False,
                    )
                    print(f"Email sent to: {student.email}")
                except Exception as e:
                    print(f"Failed to send email to: {student.email}, error: {e}")

@approved_required
@teacher_required
@superuser_required
@login_required
def create_announcement(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()    
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if request.method == 'POST':
        print("Form submitted")
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            print("Form is valid")
            announcement = form.save()

            # Schedule the async task after the response is returned
            threading.Thread(target=send_announcement_emails, args=(announcement,)).start()

            return redirect('announcements')  # Redirect to the announcements page after saving
        else:
            print("Form is not valid")
            print(form.errors)
    else:
        form = AnnouncementForm()
    if "mobile" in user_agent:
        return render(request, 'portal/mobile_announcementsCreate.html', {'form': form, "profile_photo":profile_photo})
    else:
        return render(request, 'portal/desktop_announcementCreate.html', {'form': form, "profile_photo":profile_photo})

@approved_required
@teacher_required
@superuser_required
@login_required
def gradesforAssignment(request: HttpRequest, folder_id, assignment_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    gradeArray = []
    course_id = Folder.objects.get(id = folder_id).Course_id
    Course = Courses.objects.get(id = course_id)
    for people in Course.People.all():
        try:
            grade = Grade.objects.get(assignment_id = assignment_id, course_id= course_id, user_id = people.id).grade
        except Grade.DoesNotExist:
            grade = None
        dict = {"id":people.id, "people":str(people.first_name +" "+people.last_name), "grade": grade}
        gradeArray.append(dict)
    if request.method == "POST":
        for people in gradeArray:
            grade_new = request.POST.get(str("grade_"+str(people['id'])))
            if grade_new == 'None':
                grade_new = ""
            if grade_new:
                try:
                    grade = Grade.objects.get(assignment_id = assignment_id, course_id= course_id, user_id = people['id'])
                    grade.grade = float(grade_new)
                    grade.save()
                except Grade.DoesNotExist:
                    savegrade = Grade.objects.create(assignment_id = assignment_id, course_id= course_id, user_id = people['id'], grade = grade_new)
        return redirect("gradesforAssignment", folder_id, assignment_id)
    if "mobile" in user_agent:    
        return render(request, "portal/mobile_gradeStudents.html", {"grades":gradeArray, "course":Course, "profile_photo":profile_photo})
    else:
        return render(request, "portal/desktop_gradeStudents.html", {"grades":gradeArray, "course":Course, "profile_photo":profile_photo})

@approved_required
@teacher_required
@superuser_required
@login_required
def removeStudentFromCourse(request, course_id):
    id = request.POST.get("student_id")
    student = CustomUser.objects.get(id = id)
    course = Courses.objects.get(id = course_id)
    course.People.remove(student)
    return redirect("students", course.id)

@approved_required
@teacher_required
@superuser_required
@login_required
def submissions(request: HttpRequest, folder_id, user_id, assignment_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    try:
        grade = Grade.objects.get(user_id = user_id, assignment_id= assignment_id)
    except Grade.DoesNotExist:
        grade = None
    folder = Folder.objects.get(id = folder_id)
    submissions = filestoAssignment.objects.filter(user_id =user_id, assignment_id = assignment_id)
    assignment = Assignment.objects.get(id = assignment_id)
    user = CustomUser.objects.get(id = user_id)
    if "mobile" in user_agent:
        return render(request, "portal/mobile_submissionView.html", context = {"submissions":submissions, "grade":grade, "folder":folder, "user": user, "assignment":assignment, "profile_photo":profile_photo})
    else:
        return render(request, "portal/desktop_submissionView.html", context = {"submissions":submissions, "grade":grade, "folder":folder, "user": user, "assignment":assignment, "profile_photo":profile_photo})

def PasswordResetView(request):
    if request.method == 'POST':
        email = request.POST['email']
        if CustomUser.objects.get(email = email):
            user = CustomUser.objects.get(email=email)
            current_site = get_current_site(request)
            subject = 'Reset Your Password'
            message = render_to_string('email/resetPassword.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
                'protocol': 'https' if request.is_secure() else 'http',
            })
            send_mail(subject, '', 'noreply@stlouisgurudwara.org', [user.email],  html_message=message)
            return redirect('login')
    return render(request, 'portal/passwordResetInitial.html')

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def upload_syllabus(request, course_id):
    course = Courses.objects.get(id=course_id)
    form = SyllabusUploadForm(request.POST, request.FILES, instance=course)
    if form.is_valid():
        if course.Syllabus.path and os.path.exists(course.Syllabus.path):
            os.remove(course.Syllabus.path)
        form.save()
        return redirect('courses')  

def reset(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST['password1']
            password2 = request.POST['password2']
            if password1 == password2:
                user.password = make_password(password1)
                user.save()
                return redirect('login')
        return render(request, 'portal/passwordReset.html')
    else:
        return redirect('reset')

def registration(request):
    if request.method == 'POST':
        firstname = request.POST.get('firstName')
        lastname = request.POST.get('lastName')
        email = request.POST.get('email')
        password = request.POST.get('password')
        phone = request.POST.get('phoneNumber')
        honeypot = request.POST.get('website', '').strip()
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')
        try:
            phone = validate_phone_number(phone)
            if CustomUser.objects.filter(email=email).exists():
                return redirect('login')
        except ValidationError as e:
            return render(request, "registration.html", {"error": str(e)})
        if honeypot:
            BlacklistedIP.objects.get_or_create(
                ip_address=ip,
                defaults={'reason': 'Honeypot triggered'}
            )
            return JsonResponse({"status": "bot_detected"}, status=403)
        else:
            if firstname and lastname and email and password and phone:
                CustomUser.objects.create(first_name=firstname, last_name=lastname, phone_number = phone, username = email, email=email, password= make_password(password))
                user = CustomUser.objects.get(first_name=firstname, last_name=lastname, username = email, phone_number = phone, email=email)
                current_site = get_current_site(request)
                subject = 'Activate Your Account'
                message = render_to_string('email/activation.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': default_token_generator.make_token(user),
                    'protocol': 'https' if request.is_secure() else 'http',
                })
                send_mail(subject, '', 'noreply@stlouisgurudwara.org', [user.email],  html_message=message)
                return redirect('login')
    return render(request,"registration.html")

def validate_phone_number(phone):
    phone = re.sub(r'\D', '', phone)
    if len(phone) != 10:
        raise ValidationError("Phone number must be 10 digits.")
    return phone

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return redirect('index')
    else:
        return render(request, 'portal/invalidAccountActivation.html')

@teacher_required
@superuser_required
@login_required
@require_POST
def courseAdd(request):
    title = request.POST.get('title')
    description = request.POST.get('description')
    Courses.objects.create(Title = title, Description = description)
    return redirect("courses")

@teacher_required
@superuser_required
@login_required
@require_POST
def sectionAdd(request, course_id):
    user = request.user
    course = Courses.objects.get(id = course_id)
    title = request.POST.get('title')
    Count = Section.objects.filter(Course_id = course_id).count()
    if Count is None:
            Count = 0
    Section.objects.create(Title = title, Course_id = course_id, ONum = Count)
    return redirect("course", course_id)

@teacher_required
@superuser_required
@login_required
def addStudents(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = Courses.objects.get(id=course_id)
    enrolled_students = course.People.all()
    all_students = CustomUser.objects.filter(usertype="Student").exclude(id__in=enrolled_students)
    if request.method == 'POST':
        selected_students = request.POST.getlist('selected_students')
        for student_id in selected_students:
            student = CustomUser.objects.get(id=student_id)
            course.People.add(student)
        return redirect('students', course.id)
    else:
        context = {
            'course': course,
            'all_students': all_students,
            'profile_photo':profile_photo
        }
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_studentAdd.html", context)
    else:
        return render(request, "portal/desktop_studentAdd.html", context)

def account_activation_sent(request):
    return render(request, 'portal/invalidAccountActivation.html')

@require_POST
def addKirtan(request):
    date = datetime.strptime(request.POST.get("kirtanDate"), "%Y-%m-%d")
    hostingFamily = request.POST.get("hostingFamily")
    WeeklyEmail.objects.create(email_type = "weekly", organizer = hostingFamily, date_created = datetime.today(), date_scheduled= date,  sent=False, subject ="Weekly Kirtan")
    return redirect("calenderNotification")

@login_required
@admin_required
@approved_required
def changeUserInfo(request):
    user_id = request.POST.get("user_id")
    user = CustomUser.objects.get(id = user_id)
    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    user.first_name = first_name
    user.last_name = last_name
    user.save()
    return redirect("adminUsers")

@teacher_required
@superuser_required
@login_required
@require_POST
def folderAdd(request):
    section_id = request.POST.get('section_id')
    section = Section.objects.get(id = section_id)
    course_id = section.Course_id
    title = request.POST.get('title')
    Count = Section.objects.filter(Course_id = course_id).count()
    if Count is None:
        Count = 0
    folder = Folder.objects.create(Title = title, Course_id = course_id)
    section.Folders.add(folder)
    return redirect("course", course_id)

def login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        honeypot = request.POST.get('website', '').strip()
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')
        if honeypot:
            BlacklistedIP.objects.get_or_create(
                ip_address=ip,
                defaults={'reason': 'Honeypot triggered'}
            )
            return JsonResponse({"status": "bot_detected"}, status=403)
        else:
            if email and password:
                user = authenticate(username=email, password=password)
                if user:
                    auth_login(request, user)
                    return redirect("courses")
                else:
                    return redirect("login")
    return render(request, "login.html")

@approved_required
@emailSender_required
@login_required
def calenderNotification(request: HttpRequest, year=None, month=None):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    
    # Default to current year and month if not provided
    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month
    
    # Fetch WeeklyEmail events for the given month/year
    weekly_emails = WeeklyEmail.objects.filter(
        date_scheduled__year=year,
        date_scheduled__month=month
    )
    
    # Group events by day (using the day of the month)
    events_by_day = {}
    for event in weekly_emails:
        day = event.date_scheduled.day
        events_by_day.setdefault(day, []).append(event)
    
    # Create a Calendar instance and get (day, weekday) tuples
    cal = calendar.Calendar()
    month_days = list(cal.itermonthdays2(year, month))
    today = datetime.now().day if year == datetime.now().year and month == datetime.now().month else None
    print(today)
    # Calculate previous and next month/year for navigation
    prev_month = month - 1
    next_month = month + 1
    prev_year = year
    next_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    if next_month == 13:
        next_month = 1
        next_year += 1
    weeks = []
    week = [None] * 7
    for day, weekday in month_days:
        if day != 0:
            week[weekday] = {'day': day, 'events': events_by_day.get(day, [])}
        if weekday == 6:
            weeks.append(week)
            week = [None] * 7
    if any(cell is not None for cell in week):
        weeks.append(week)
    
    context = {
        'year': year,
        'month': month,
        'month_days': month_days,  # raw (day, weekday) tuples, if needed
        'today': today,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'weeks': weeks,  # List of weeks, each week is a list of 7 cells (None or dict with day and events)
        'profile_photo': profile_photo,
    }
    
    if "mobile" in user_agent:
        return render(request, "portal/mobile_adminCalender.html", context)
    else:   
        return render(request, "portal/desktop_adminCalender.html", context)

def delete_email(request, email_id):
    email = WeeklyEmail.objects.get(id=email_id)
    email.delete()
    return redirect('calenderNotification')

def calendarEventView(request: HttpRequest, email_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    email = WeeklyEmail.objects.get(id = email_id)
    date = email.date_scheduled
    day = date.strftime("%A")
    date = date.strftime("%B %d, %Y")
    if email.email_type == "weekly":
        if "mobile" in user_agent:
            return render(request, "portal/mobile_adminCalenderView.html", {"email":email, "day":day, 'profile_photo':profile_photo})
        else:   
            return render(request, "portal/desktop_adminCalenderView.html", {"email":email, "day":day, 'profile_photo':profile_photo})
    else:
        redirect("calenderNotification")