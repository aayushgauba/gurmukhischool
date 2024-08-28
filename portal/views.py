from django.shortcuts import render, redirect
from portal.models import CustomUser, Courses, Section, Folder, Grade, Announcement, Attendance, CarouselImage
from django.contrib.auth.hashers import make_password, check_password
from django.http import HttpRequest
from django.contrib.auth import authenticate, login as auth_login, logout
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.http import HttpResponse
from django.contrib.auth.tokens import default_token_generator
from .forms import UploadedFileForm, FileUploadForm, AnnouncementForm, ProfilePhotoForm, CarouselImageForm, SyllabusUploadForm
from .models import UploadedFile, Assignment, filestoAssignment
from django.contrib.auth.decorators import login_required
from .decorators import superuser_required, teacher_required, admin_required, approved_required
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

@approved_required
@login_required
def course(request: HttpRequest, course_id):
    user = request.user
    course = Courses.objects.get(id = course_id)
    if request.user.usertype == 'Teacher':
        sections = Section.objects.filter(Course_id = course.id).order_by("ONum")
    elif request.user.usertype == 'Student':
        sections = Section.objects.filter(Course_id = course.id, Status = True).order_by("ONum")
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_course.html", {"course":course, "user":user, "sections":sections})
    else:   
        return render(request, "portal/desktop_course.html", {"course":course, "user":user, "sections":sections})

@approved_required
@teacher_required
@superuser_required
@login_required
def students(request: HttpRequest, course_id):
    course = Courses.objects.get(id = course_id)
    students = course.People.all()
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_students.html", {"students":students, "course":course})
    else:
        return render(request, "portal/desktop_students.html", {"students":students, "course":course})

@approved_required
@login_required
def fileView(request, file_id):
    file = UploadedFile.objects.get(id = file_id)
    context = {
        'file': file,
        'file_type': file.file.url.split('.')[-1].lower()
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
def carousel_management(request):
    images = CarouselImage.objects.all()
    images = images.order_by("order")
    if images:
        count = images.count()
    else:
        count = 0
    if request.method == 'POST':
        form = CarouselImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save()
            image.order = count
            image.save() 
            return redirect('carousel_management')
    else:
        form = CarouselImageForm()
    return render(request, 'portal/adminCarousel.html', {'images': images, 'form': form})

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
def delete_carousel_image(request):
    if request.method == 'POST':
        image_id = request.POST.get('image_id')
        image =  CarouselImage.objects.get(id=image_id)
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
    studentform = FileUploadForm(user_id = request.user.id, assignment_id = assignment_id)
    if not request.user.is_superuser and request.user.usertype == "Student":
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

@approved_required
@login_required
def courses(request: HttpRequest):
    user = request.user
    form = SyllabusUploadForm()
    courses = None
    if user.usertype == "Teacher":
        courses = Courses.objects.all().order_by("id")
    elif user.usertype == "Student":
        courses = Courses.objects.filter(People = request.user).order_by("id")
    elif user.usertype == "Admin" and user.is_superuser:
        return redirect("adminViewHome")
    else:
        return render(request, "portal/unknown_usertype.html", {"user": user})
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if "mobile" in user_agent:
        return render(request, 'portal/mobile_courses.html', {"user": user, "courses": courses, "form": form})
    else:
        return render(request, "portal/desktop_courses.html", {"user": user, "courses": courses, "form": form})


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
def grades(request: HttpRequest, course_id):
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    grades = Grade.objects.filter(course_id = course_id)
    if grades:
        if not request.user.is_superuser and request.user.usertype == "Student":
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
                return render(request, "portal/desktop_grades.html", {"grades":gradeArray, "course":course, "final":finals})
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
                return render(request, "portal/desktop_grades.html", {"grades":gradeArray, "course":course, "final":finals})
    else:
        course = Courses.objects.get(id = course_id)
        if "mobile" in user_agent:
            return render(request, "portal/mobile_grades.html", {"course":course})
        else:
            return render(request, "portal/desktop_grades.html", {"course":course})

@approved_required
def announcements(request: HttpRequest):
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
        return render(request, "portal/desktop_announcements.html", {"announcements": announcements})

@approved_required
@teacher_required
@superuser_required
@login_required
def mark_attendance(request: HttpRequest, course_id, day, month, year):
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
            'attendance_dict': attendanceArray
        }
        user_agent = request.META['HTTP_USER_AGENT'].lower()
        if "mobile" in user_agent:
            return render(request, 'portal/mobile_attendanceAdd.html', context)
        else:
            return render(request, 'portal/desktop_attendanceAdd.html', context)

@approved_required
@login_required
def attendance(request: HttpRequest, course_id, year=None, month=None):
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    course = Courses.objects.get(id = course_id)
    if not year or not month:
        # Default to the current year and month if none are provided
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
        print(absent_days)
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
    }
    else:
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
    }
    if "mobile" in user_agent:        
        return render(request, 'portal/mobile_attendance.html', context)
    else:
        return render(request, 'portal/desktop_attendance.html', context)


@login_required
@admin_required
@approved_required
def adminViewHome(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user_type = request.POST.get('user_type')
        user = CustomUser.objects.get(id=user_id)
        user.usertype = user_type
        if user.usertype == "Teacher" or "Admin":
            user.is_superuser = True
        elif user.usertype == "Student":
            user.is_superuser = False
        user.approved = True
        user.save()
        current_site = get_current_site(request)
        subject = 'Account approved'
        message = render_to_string('email/accountApproved.html', {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
            'protocol': 'https' if request.is_secure() else 'http',
        })
        send_mail(subject, '', 'gurmukhischoolstl@outlook.com', [user.email],  html_message=message)
        return redirect("adminViewHome")
    users = CustomUser.objects.filter(approved = False)
    return render(request, "portal/adminHome.html", {"users":users})

@login_required
@admin_required
@approved_required
def adminUsers(request):
    users = CustomUser.objects.filter(approved = True)
    return render(request, "portal/adminUsers.html", {"users":users})

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
def adminContactView(request):
    contacts = Contact.objects.all()
    return render(request, 'portal/adminContact.html', {"contacts":contacts})

@login_required
@approved_required
@require_POST
def upload_profile_photo(request, course_id=None):
    form = ProfilePhotoForm(request.POST, request.FILES, instance=request.user)
    if form.is_valid():
        if request.user.profile_photo.path and os.path.exists(request.user.profile_photo.path):
            os.remove(request.user.profile_photo.path)
        form.save()
        if course_id:
            return redirect('profile', course_id=course_id)
        else:
            return redirect('profile')
    return render(request, 'upload_profile_photo.html', {'form': form})

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
    form = ProfilePhotoForm()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_profile.html", {'course': course, 'user': user, 'form': form})
    else:
        return render(request, "portal/desktop_profile.html", {'course': course, 'user': user, 'form': form})

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
                        from_email='gurmukhischoolstl@outlook.com',
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
        return render(request, 'portal/mobile_announcementsCreate.html', {'form': form})
    else:
        return render(request, 'portal/desktop_announcementCreate.html', {'form': form})

@approved_required
@teacher_required
@superuser_required
@login_required
def gradesforAssignment(request: HttpRequest, folder_id, assignment_id):
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
            if grade_new is not None:
                try:
                    grade = Grade.objects.get(assignment_id = assignment_id, course_id= course_id, user_id = people['id'])
                    grade.grade = grade_new
                    grade.save()
                except Grade.DoesNotExist:
                    savegrade = Grade.objects.create(assignment_id = assignment_id, course_id= course_id, user_id = people['id'], grade = grade_new)
        return redirect("gradesforAssignment", folder_id, assignment_id)
    if "mobile" in user_agent:    
        return render(request, "portal/mobile_gradeStudents.html", {"grades":gradeArray, "course":Course})
    else:
        return render(request, "portal/desktop_gradeStudents.html", {"grades":gradeArray, "course":Course})

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
        return render(request, "portal/mobile_submissionView.html", context = {"submissions":submissions, "grade":grade, "folder":folder, "user": user, "assignment":assignment})
    else:
        return render(request, "portal/desktop_submissionView.html", context = {"submissions":submissions, "grade":grade, "folder":folder, "user": user, "assignment":assignment})

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
            send_mail(subject, '', 'gurmukhischoolstl@outlook.com', [user.email],  html_message=message)
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
        try:
            # Validate and format the phone number
            phone = validate_phone_number(phone)

            if CustomUser.objects.filter(email=email).exists():
                return redirect('login')
            
        except ValidationError as e:
            # Handle validation error by rendering the form again with an error message
            return render(request, "registration.html", {"error": str(e)})
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
            send_mail(subject, '', 'gurmukhischoolstl@outlook.com', [user.email],  html_message=message)
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
            'all_students': all_students
        }
    user_agent = request.META['HTTP_USER_AGENT'].lower()
    if "mobile" in user_agent:
        return render(request, "portal/mobile_studentAdd.html", context)
    else:
        return render(request, "portal/desktop_studentAdd.html", context)

@login_required
def stuMode(request):
    user = request.user
    change = CustomUser.objects.get(username = user.username)
    change.usertype = "Teacher"
    change.is_superuser = True
    change.save()

def account_activation_sent(request):
    return render(request, 'portal/invalidAccountActivation.html')

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
        if email and password:
            user = authenticate(username=email, password=password)
            if user:
                auth_login(request, user)
                return redirect("courses")
            else:
                return redirect("login")
    return render(request, "login.html")