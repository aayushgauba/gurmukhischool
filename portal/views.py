from django.shortcuts import render, redirect
from portal.models import CustomUser, Courses, Section, Folder, Grade, Announcement, Attendance
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate, login as auth_login, logout
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from .forms import UploadedFileForm, FileUploadForm, AnnouncementForm, ProfilePhotoForm
from .models import UploadedFile, Assignment, filestoAssignment
from django.contrib.auth.decorators import login_required
from .decorators import superuser_required, teacher_required
from django.views.decorators.http import require_POST
from asgiref.sync import sync_to_async
import os
import asyncio
import threading
import calendar
from datetime import datetime

@login_required
def course(request, course_id):
    user = request.user
    course = Courses.objects.get(id = course_id)
    if request.user.usertype == 'Teacher':
        sections = Section.objects.filter(Course_id = course.id).order_by("ONum")
    elif request.user.usertype == 'Student':
        sections = Section.objects.filter(Course_id = course.id, Status = True).order_by("ONum")
    return render(request, "portal/course.html", {"course":course, "user":user, "sections":sections})

@teacher_required
@superuser_required
@login_required
def students(request, course_id):
    course = Courses.objects.get(id = course_id)
    students = course.People.all()
    return render(request, "portal/students.html", {"students":students, "course":course})

@login_required
def fileView(request, file_id):
    file = UploadedFile.objects.get(id = file_id)
    context = {
        'file': file,
        'file_type': file.file.url.split('.')[-1].lower()
    }
    return render(request, 'portal/fileDetail.html', context)

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

@require_POST
@login_required
def submitFilesToAssignment(request, section_id, folder_id, assignment_id):
    if request.method == "POST":
        form = FileUploadForm(request.POST, request.FILES, user_id = request.user.id, assignment_id = assignment_id)
        if form.is_valid():
            form.save()
            return redirect("viewAssignment", section_id, folder_id, assignment_id)

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

@login_required
def viewAssignment(request, section_id, folder_id, assignment_id):
    assignment = Assignment.objects.get(id = assignment_id)
    files = UploadedFile.objects.all()
    form = UploadedFileForm()
    studentform = FileUploadForm(user_id = request.user.id, assignment_id = assignment_id)
    if not request.user.is_superuser and request.user.usertype == "Student":
        submissions = filestoAssignment.objects.filter(user_id = request.user.id, assignment_id = assignment_id)
        context = {"submissions":submissions, "assignment":assignment, "form":form, "studentform":studentform, "files":files, "section_id":section_id, "folder_id":folder_id}
    elif request.user.is_superuser and request.user.usertype == "Teacher":
        submissions = filestoAssignment.objects.filter(assignment_id = assignment_id).distinct()
        users = CustomUser.objects.filter(id__in=filestoAssignment.objects.filter(assignment_id=assignment.id).values('user_id').distinct())
        context = {"submissions":submissions, "assignment":assignment, "users":users, "form":form, "studentform":studentform, "files":files, "section_id":section_id, "folder_id":folder_id}
    files = files.exclude(id__in = assignment.files.values_list('id', flat=True))
    return render(request, "portal/assignmentDetail.html", context = context)

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

@teacher_required
@superuser_required
@require_POST
@login_required
def deleteAssignment(request, section_id, folder_id, assignment_id):
    if request.method == 'POST':
        assignment = Assignment.objects.get(id = assignment_id)
        assignment.delete()
        return redirect('folder',section_id, folder_id)

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

@login_required
def folder(request, section_id, folder_id):
    user = request.user
    form = UploadedFileForm()
    folder = Folder.objects.get(id = folder_id)
    course = Courses.objects.get(id = folder.Course_id)
    return render(request, "portal/folderView.html", {"course":course, "user":user, "form":form, "folder":folder, "section_id":section_id})

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

@login_required
def courses(request):
    user = request.user
    if request.user.usertype == "Teacher" and request.user.is_superuser:
        courses = Courses.objects.all()
    elif request.user.usertype == "Student" and not request.user.is_superuser:
        courses = Courses.objects.filter(People = user)
    return render(request, "portal/courses.html", {"user":user, "courses":courses})

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

@login_required
def grades(request, course_id):
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
            return render(request, "portal/grades.html", {"grades":gradeArray, "course":course, "final":finals})
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
            return render(request, "portal/grades.html", {"grades":gradeArray, "course":course, "final":finals})
    else:
        course = Courses.objects.get(id = course_id)
        return render(request, "portal/grades.html", {"grades":[], "course":course, "final":0})

def announcements(request):
    if request.user.usertype == "Teacher" and request.user.is_superuser:
        announcements = Announcement.objects.all()
    elif request.user.usertype == "Student" and not request.user.is_superuser:
        student = CustomUser.objects.get(id=request.user.id)
        courses = Courses.objects.filter(People=student)
        announcements = Announcement.objects.filter(recipients__in=courses)
    else:
        announcements = Announcement.objects.none()  # Handle other user types if necessary

    return render(request, "portal/announcements.html", {"announcements": announcements})

@teacher_required
@superuser_required
@login_required
def mark_attendance(request, course_id, day, month, year):
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
        return render(request, 'portal/attendanceAdd.html', context)

@login_required
def attendance(request, course_id, year=None, month=None):
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
    return render(request, 'portal/attendance.html', context)

@require_POST
@login_required
def upload_profile_photo(request, course_id):
    if request.method == 'POST':
        form = ProfilePhotoForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile', course_id)  # Redirect to the user's profile page or any other page
    else:
        form = ProfilePhotoForm(instance=request.user)
    return render(request, 'upload_profile_photo.html', {'form': form})

@require_POST
@login_required
def upload_profile_photo(request):
    if request.method == 'POST':
        form = ProfilePhotoForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')  # Redirect to the user's profile page or any other page
    else:
        form = ProfilePhotoForm(instance=request.user)
    return render(request, 'upload_profile_photo.html', {'form': form})

@login_required
def signout(request):
    logout(request) 
    return redirect('login')

@login_required
def profile(request, course_id):
    course = Courses.objects.get(id = course_id)
    user = request.user
    form = ProfilePhotoForm()
    return render(request, 'portal/profile.html', {'course':course, 'user':user, "form":form,})

@login_required
def profile(request):
    user = request.user
    form = ProfilePhotoForm()
    return render(request, 'portal/profile.html', {'course':course, 'user':user, "form":form})

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

@teacher_required
@superuser_required
@login_required
def create_announcement(request):
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
    return render(request, 'portal/announcementCreate.html', {'form': form})

@teacher_required
@superuser_required
@login_required
def gradesforAssignment(request, folder_id, assignment_id):
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
    return render(request, "portal/gradeStudents.html", {"grades":gradeArray, "course":Course})

@teacher_required
@superuser_required
@login_required
def submissions(request, folder_id, user_id, assignment_id):
    try:
        grade = Grade.objects.get(user_id = user_id, assignment_id= assignment_id)
    except Grade.DoesNotExist:
        grade = None
    folder = Folder.objects.get(id = folder_id)
    submissions = filestoAssignment.objects.filter(user_id =user_id, assignment_id = assignment_id)
    assignment = Assignment.objects.get(id = assignment_id)
    user = CustomUser.objects.get(id = user_id)
    return render(request, "portal/submissionView.html", context = {"submissions":submissions, "grade":grade, "folder":folder, "user": user, "assignment":assignment})

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
        if firstname and lastname and email and password:
            CustomUser.objects.create(first_name=firstname, last_name=lastname, username = email, email=email, password= make_password(password))
            user = CustomUser.objects.get(first_name=firstname, last_name=lastname, username = email, email=email)
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
            return redirect('account_activation_sent')
    return render(request,"registration.html")



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
def addStudents(request, course_id):
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
        return render(request, "portal/studentAdd.html", context)

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
                print(user.email)
                return redirect("courses")
            else:
                return render(request, "login.html", {"error": "Invalid credentials"})
    return render(request, "login.html")