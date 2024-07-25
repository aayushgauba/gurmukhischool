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
from .models import UploadedFile

def course(request, course_id):
    user = request.user
    course = Courses.objects.get(id = course_id)
    sections = Section.objects.filter(Course_id = course.id).order_by("ONum")
    folders = Folder.objects.filter(id = course_id)
    files  = UploadedFile.objects.all()
    return render(request, "portal/course.html", {"course":course, "user":user, "sections":sections, "folders":folders, "files":files})

def uploadFile(request, section_id, folder_id):
    if request.method == 'POST':
        form = UploadedFileForm(request.POST, request.FILES, folder_id=folder_id)
        if form.is_valid():
            form.save()
            return redirect('success')
    else:
        form = UploadedFileForm(folder_id=folder_id)
    return render(request, 'portal/fileAdd.html', {'form': form})

def folder(request, section_id, folder_id):
    user = request.user
    folder = Folder.objects.get(id = folder_id)
    course = Courses.objects.get(id = folder.Course_id)
    return render(request, "portal/folderView.html", {"course":course, "user":user, "folder":folder, "section_id":section_id})

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

def changeVisibility(request, section_id):
    section = Section.objects.get(id = section_id)
    if section.Status == True:
        section.Status = False
    else:
        section.Status = True
    section.save()
    course_id = section.Course_id
    return redirect("course", course_id)



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

def courseAdd(request):
    user = request.user
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        Courses.objects.create(Title = title, Description = description)
        return redirect("courses")
    return render(request,"portal/courseAdd.html", {"user":user})

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


def stuMode(request):
    user = request.user
    change = CustomUser.objects.get(username = user.username)
    change.usertype = "Teacher"
    change.save()

def account_activation_sent(request):
    return render(request, 'portal/invalidAccountActivation.html')

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
        Folder.objects.create(Title = title, Course_id = course_id, Section_id = section.id)
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