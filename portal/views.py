from django.shortcuts import render, redirect
from portal.models import CustomUser, Courses, Section, Folder
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from .forms import UploadedFileForm
from .models import UploadedFile, Assignment
from django.contrib.auth.decorators import login_required
from .decorators import superuser_required, teacher_required
from django.views.decorators.http import require_POST
import os


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
    students = CustomUser.objects.filter(usertype = 'Student')
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
    files = files.exclude(id__in = assignment.files.values_list('id', flat=True))
    form = UploadedFileForm()
    return render(request, "portal/assignmentDetail.html", {"assignment":assignment, "form":form, "files":files, "section_id":section_id, "folder_id":folder_id})

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
    courses = Courses.objects.all()
    if user:
        return render(request, "portal/courses.html", {"user":user, "courses":courses})
    else:
        return redirect("index")


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

@login_required
def courseAdd(request):
    user = request.user
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        Courses.objects.create(Title = title, Description = description)
        return redirect("courses")
    return render(request,"portal/courseAdd.html", {"user":user})

@teacher_required
@superuser_required
@login_required
def sectionAdd(request, course_id):
    user = request.user
    course = Courses.objects.get(id = course_id)
    if request.method == 'POST':
        title = request.POST.get('title')
        Count = Section.objects.filter(Course_id = course_id).count()
        if Count is None:
            Count = 0
        Section.objects.create(Title = title, Course_id = course_id, ONum = Count)
        return redirect("course", course_id)
    return render(request,"portal/sectionAdd.html", {"user":user, "course":course})

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
def folderAdd(request, section_id):
    user = request.user
    section = Section.objects.get(id = section_id)
    course_id = section.Course_id
    course = Courses.objects.get(id = course_id)
    if request.method == 'POST':
        title = request.POST.get('title')
        Count = Section.objects.filter(Course_id = course_id).count()
        if Count is None:
            Count = 0
        folder = Folder.objects.create(Title = title, Course_id = course_id)
        section.Folders.add(folder)
        return redirect("course", course_id)
    return render(request,"portal/folderAdd.html", {"user":user, "course":course, "section":section})    

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