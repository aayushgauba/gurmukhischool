from django.shortcuts import render, redirect, get_object_or_404
from portal.models import CustomUser, Schedule, WeeklyEmail, Course, Section, Folder, Grade, Announcement, Attendance, CarouselImage
from django.http import HttpRequest, JsonResponse, FileResponse, Http404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from main.models import BlacklistedIP
from django.http import HttpResponse
from django.contrib.auth.tokens import default_token_generator
from .forms import UploadedFileForm, FileUploadForm, AnnouncementForm,UploadedAttendanceForm,GroupPhotoUploadForm, ProfilePhotoForm, CarouselImageForm, SyllabusUploadForm
from .models import UploadedFile, Assignment, Submission
from main.models import CarouselImage as Carousel
from main.forms import CarouselImageForm as MainCarouselImageForm
from django.contrib.auth.decorators import login_required
from .decorators import superuser_required, teacher_required, admin_required, approved_required, emailSender_required
from django.views.decorators.http import require_POST
from asgiref.sync import sync_to_async
from pages.models import Contact
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Avg
import re
import os
import asyncio
import calendar
from datetime import datetime
import json
import mimetypes


def _user_agent(request):
    return request.META.get('HTTP_USER_AGENT', '').lower()


def _parse_grade(value):
    try:
        grade = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Grade must be a number.")
    if not 0 <= grade <= 100:
        raise ValidationError("Grade must be between 0 and 100.")
    return grade


def _is_teacher(user):
    return user.is_superuser and user.user_type == CustomUser.TEACHER


def _can_access_course(user, course):
    return _is_teacher(user) or (
        user.user_type == CustomUser.STUDENT
        and course.people.filter(pk=user.pk).exists()
    )


def _require_course_access(user, course):
    if not _can_access_course(user, course):
        raise PermissionDenied


def _stored_file_response(field_file, *, content_type=None):
    if not field_file or not field_file.name:
        raise Http404("File not found.")
    try:
        if not field_file.storage.exists(field_file.name):
            raise Http404("File not found.")
        file_handle = field_file.open("rb")
    except Http404:
        raise
    except (OSError, ValueError) as exc:
        raise Http404("File not found.") from exc

    detected_type = content_type or mimetypes.guess_type(field_file.name)[0]
    return FileResponse(
        file_handle,
        content_type=detected_type or "application/octet-stream",
        as_attachment=False,
        filename=os.path.basename(field_file.name),
    )


def _course_graph(section_id=None, folder_id=None, assignment_id=None):
    section = get_object_or_404(Section, pk=section_id) if section_id is not None else None
    folder = get_object_or_404(Folder, pk=folder_id) if folder_id is not None else None
    if section and folder and not section.folders.filter(pk=folder.pk).exists():
        raise Http404
    assignment = get_object_or_404(Assignment, pk=assignment_id) if assignment_id is not None else None
    if folder and assignment and not folder.assignments.filter(pk=assignment.pk).exists():
        raise Http404
    course_id = folder.course_id if folder else section.course_id
    course = get_object_or_404(Course, pk=course_id)
    return course, section, folder, assignment

@approved_required
@login_required
def course(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user = request.user
    course = get_object_or_404(Course, id=course_id)
    _require_course_access(request.user, course)
    sections = Section.objects.filter(course_id=course.id)
    if not _is_teacher(request.user):
        sections = sections.filter(status=True)
    sections = sections.order_by("order").prefetch_related(
        "folders",
        "folders__files",
        "folders__assignments",
    )
    return render(request, "portal/course.html", {
        "course": course,
        "profile_photo": profile_photo,
        "user": user,
        "sections": sections,
        "active_nav": "courses",
    })

@approved_required
@teacher_required
@superuser_required
@login_required
def students(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = Course.objects.get(id = course_id)
    students = course.people.all()
    user_agent = _user_agent(request)
    if "mobile" in user_agent:
        return render(request, "portal/mobile_students.html", {"students":students,"profile_photo":profile_photo, "course":course})
    else:
        return render(request, "portal/desktop_students.html", {"students":students, "profile_photo":profile_photo, "course":course})

@approved_required
@login_required
def fileView(request, file_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    file = get_object_or_404(UploadedFile, id=file_id)
    course_ids = set(Folder.objects.filter(files=file).values_list('course_id', flat=True))
    course_ids.update(Folder.objects.filter(
        Assignments__files=file
    ).values_list('course_id', flat=True))
    courses = Course.objects.filter(pk__in=course_ids)
    if not any(_can_access_course(request.user, course) for course in courses):
        raise PermissionDenied
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
    _, _, folder, _ = _course_graph(section_id, folder_id)
    file = get_object_or_404(folder.files, pk=pk)
    if request.method == 'POST':
        folder.files.remove(file)
        if not Folder.objects.filter(files=file).exists() and not Assignment.objects.filter(
            files=file
        ).exists():
            if file.file and os.path.exists(file.file.path):
                os.remove(file.file.path)
            file.delete()
        return redirect('folder', section_id, folder_id)

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def addExistingFilesToAssignment(request, section_id, folder_id, assignment_id):
    _course_graph(section_id, folder_id, assignment_id)
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
    user_agent = _user_agent(request)
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
@require_POST
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
@require_POST
def moveMainCarouselImageDown(request, image_id):
    image = Carousel.objects.get(id = image_id)
    order = image.order
    if order is not None and order < Carousel.objects.count() - 1:
        newImage = Carousel.objects.get(order = (order+1))
        image.order = order +1
        newImage.order = order
        image.save()
        newImage.save()
    return redirect("carousel_management")

@login_required
@approved_required
@admin_required
@require_POST
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
@require_POST
def moveCarouselImageDown(request, image_id):
    image = CarouselImage.objects.get(id = image_id)
    order = image.order
    if order is not None and order < CarouselImage.objects.count() - 1:
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
        for order, remaining in enumerate(CarouselImage.objects.order_by('order', 'id')):
            if remaining.order != order:
                remaining.order = order
                remaining.save(update_fields=['order'])
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
        for order, remaining in enumerate(Carousel.objects.order_by('order', 'id')):
            if remaining.order != order:
                remaining.order = order
                remaining.save(update_fields=['order'])
        return redirect('carousel_management')

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def addNewFilesToAssignment(request, section_id, folder_id, assignment_id):
    _course_graph(section_id, folder_id, assignment_id)
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
    course, _, _, _ = _course_graph(section_id, folder_id, assignment_id)
    _require_course_access(request.user, course)
    if request.user.user_type != CustomUser.STUDENT:
        raise PermissionDenied
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
    _course_graph(section_id, folder_id, assignment_id)
    if request.method == "POST":
        file_id = request.POST.get('file_id')
        assignment = Assignment.objects.get(id = assignment_id)
        file = UploadedFile.objects.get(id = file_id)
        assignment.files.remove(file)
        used_by_folder = Folder.objects.filter(files=file).exists()
        used_by_assignment = Assignment.objects.filter(files=file).exists()
        if not used_by_folder and not used_by_assignment:
            if file.file.path and os.path.exists(file.file.path):
                os.remove(file.file.path)
                file.delete()
            elif file.file.path and not os.path.exists(file.file.path):
                file.delete()
        return redirect("viewAssignment", section_id, folder_id, assignment_id)

@approved_required
@login_required
def viewAssignment(request: HttpRequest, section_id, folder_id, assignment_id):
    course, _, folder, assignment = _course_graph(section_id, folder_id, assignment_id)
    _require_course_access(request.user, course)
    files = UploadedFile.objects.all()
    form = UploadedFileForm()
    context = {}
    studentform = FileUploadForm(user_id = request.user.id, assignment_id = assignment_id)
    if request.user.user_type == CustomUser.STUDENT:
        submissions = Submission.objects.filter(user_id = request.user.id, assignment_id = assignment_id)
        context = {"submissions":submissions,"course":course, "assignment":assignment, "folder":folder,"form":form, "studentform":studentform, "files":files, "section_id":section_id, "folder_id":folder_id}
    elif _is_teacher(request.user):
        submissions = Submission.objects.filter(assignment_id = assignment_id).distinct()
        users = CustomUser.objects.filter(id__in=Submission.objects.filter(assignment_id=assignment.id).values('user_id').distinct())
        context = {"submissions":submissions, "assignment":assignment, "course":course, "users":users, "folder":folder, "form":form, "studentform":studentform, "files":files, "section_id":section_id, "folder_id":folder_id}
    files = files.exclude(id__in = assignment.files.values_list('id', flat=True))
    user_agent = _user_agent(request)
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
    _course_graph(section_id, folder_id)
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        due_date = request.POST.get('due_date')
        assignment = Assignment.objects.create(title = title, description = description, due_date = due_date)
        folder = Folder.objects.get(id = folder_id)
        folder.assignments.add(assignment)
        return redirect('folder', section_id, folder_id)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def editAssignment(request, section_id, folder_id, assignment_id):
    _course_graph(section_id, folder_id, assignment_id)
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
    _course_graph(section_id, folder_id, assignment_id)
    if request.method == 'POST':
        assignment = Assignment.objects.get(id = assignment_id)
        assignment.delete()
        return redirect('folder',section_id, folder_id)

@approved_required
@require_POST
@login_required
def deleteSubmission(request, section_id, folder_id, assignment_id):
    course, _, _, _ = _course_graph(section_id, folder_id, assignment_id)
    _require_course_access(request.user, course)
    if request.method == 'POST':
        submission_id = request.POST.get('submission_id')
        submission = get_object_or_404(
            Submission,
            id=submission_id,
            assignment_id=assignment_id,
            user_id=request.user.id,
        )
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
    _course_graph(section_id, folder_id)
    form = UploadedFileForm(request.POST, request.FILES)
    if form.is_valid():
        uploaded_file = form.save()
        folder = Folder.objects.get(id=folder_id)
        folder.files.add(uploaded_file)
        messages.success(request, "The file was uploaded.")
    else:
        messages.error(
            request,
            "The file could not be uploaded. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )
    return redirect("folder", section_id, folder_id)

@approved_required
@login_required
def folder(request: HttpRequest, section_id, folder_id):
    user = request.user
    form = UploadedFileForm()
    course, section, folder, _ = _course_graph(section_id, folder_id)
    _require_course_access(request.user, course)
    if not _is_teacher(request.user) and not section.status:
        raise PermissionDenied
    profile_photo = request.user.profile_photos.order_by("-uploaded_at").first()
    return render(request, "portal/folder.html", {
        "course": course,
        "section": section,
        "user": user,
        "form": form,
        "folder": folder,
        "section_id": section_id,
        "profile_photo": profile_photo,
        "active_nav": "courses",
    })

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def moveSectionUp(request, section_id):
    section = Section.objects.get(id = section_id)
    course_id = section.course_id
    if section.order >0:
        section_new = Section.objects.get(order = int(section.order - 1), course_id = section.course_id)
        section.order = section.order -1
        section.save()
        section_new.order = section_new.order + 1
        section_new.save()
    return redirect("course", course_id)

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def moveSectionDown(request, section_id):
    section = Section.objects.get(id = section_id)
    count = Section.objects.filter(course_id = section.course_id).count()
    if count is None:
        count = 0
    course_id = section.course_id
    if section.order < count - 1:
        section_new = Section.objects.get(order = int(section.order + 1), course_id = section.course_id)
        section.order = section.order +1
        section.save()
        section_new.order = section_new.order - 1
        section_new.save()
    return redirect("course", course_id)

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def changeVisibility(request, section_id):
    section = Section.objects.get(id = section_id)
    if section.status == True:
        section.status = False
    else:
        section.status = True
    section.save()
    course_id = section.course_id
    return redirect("course", course_id)

@approved_required
@login_required
def view_syllabus(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    _require_course_access(request.user, course)
    if course.syllabus:
        return _stored_file_response(course.syllabus, content_type="application/pdf")
    else:
        return HttpResponse("No syllabus available.", content_type='text/plain')
    
@approved_required
@login_required
def viewMobileContentUpload(request, file_id):
    file = get_object_or_404(UploadedFile, id=file_id)
    course_ids = set(Folder.objects.filter(files=file).values_list('course_id', flat=True))
    course_ids.update(Folder.objects.filter(
        Assignments__files=file
    ).values_list('course_id', flat=True))
    if not any(
        _can_access_course(request.user, course)
        for course in Course.objects.filter(pk__in=course_ids)
    ):
        raise PermissionDenied
    return _stored_file_response(file.file)


@approved_required
@login_required
def view_submission_file(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    folders = Folder.objects.filter(Assignments__id=submission.assignment_id)
    if submission.user_id != request.user.id and not (
        _is_teacher(request.user) and folders.exists()
    ):
        raise PermissionDenied
    return _stored_file_response(submission.file)

@approved_required
@login_required
def courses(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user = request.user
    courses = None
    if user.user_type == CustomUser.TEACHER:
        courses = Course.objects.all().order_by("title")
    elif user.user_type == CustomUser.STUDENT:
        courses = Course.objects.filter(people=request.user).order_by("title")
    elif user.user_type == CustomUser.ADMIN and user.is_superuser:
        return redirect("adminViewHome")
    elif user.user_type == CustomUser.EMAIL_SENDER:
        return redirect("calenderNotification")
    else:
        return render(request, "portal/unknown_usertype.html", {"user": user})
    return render(
        request,
        "portal/courses.html",
        {
            "user": user,
            "profile_photo": profile_photo,
            "courses": courses,
            "active_nav": "courses",
        },
    )



@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def assignGradeToAssignment(request, folder_id, user_id, assignment_id, course_id):
    _, _, folder, assignment = _course_graph(
        folder_id=folder_id,
        assignment_id=assignment_id,
    )
    if folder.course_id != course_id:
        raise Http404
    course = get_object_or_404(Course, id=course_id)
    if not course.people.filter(id=user_id, user_type=CustomUser.STUDENT).exists():
        raise Http404
    try:
        new_grade = _parse_grade(request.POST.get("grade"))
    except ValidationError as error:
        return JsonResponse({"detail": error.message}, status=400)
    Grade.objects.update_or_create(
        user_id=user_id,
        assignment_id=assignment_id,
        course_id=course_id,
        defaults={"grade": new_grade},
    )
    return redirect("submissions", folder_id, user_id, assignment_id)

@approved_required
@login_required
def grades(request: HttpRequest, course_id = None):
    user_agent = _user_agent(request)
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    if course_id is not None:
        course = get_object_or_404(Course, id=course_id)
        _require_course_access(request.user, course)
        grade_array = []
        if request.user.user_type == CustomUser.STUDENT:
            student_grades = Grade.objects.filter(
                user_id=request.user.id,
                course_id=course_id,
            )
            assignments = {
                assignment.id: assignment
                for assignment in Assignment.objects.filter(
                    id__in=student_grades.values_list('assignment_id', flat=True)
                )
            }
            for grade in student_grades:
                assignment = assignments.get(grade.assignment_id)
                if assignment:
                    grade_array.append({
                        "title": assignment.title,
                        "grade": grade.grade,
                    })
        elif _is_teacher(request.user):
            assignment_ids = Folder.objects.filter(
                course_id=course_id
            ).values_list('Assignments__id', flat=True)
            assignments = Assignment.objects.filter(
                id__in=assignment_ids
            ).distinct()
            averages = {
                row['assignment_id']: row['average']
                for row in Grade.objects.filter(
                    course_id=course_id,
                    assignment_id__in=assignments.values_list('id', flat=True),
                ).values('assignment_id').annotate(average=Avg('grade'))
            }
            grade_array = [
                {"title": assignment.title, "grade": averages[assignment.id]}
                for assignment in assignments
                if assignment.id in averages
            ]

        final = (
            sum(item["grade"] for item in grade_array) / len(grade_array)
            if grade_array else None
        )
        template = (
            "portal/mobile_grades.html"
            if "mobile" in user_agent
            else "portal/desktop_grades.html"
        )
        return render(request, template, {
            "grades": grade_array,
            "course": course,
            "final": final,
            "profile_photo": profile_photo,
        })

    if not _is_teacher(request.user):
        return redirect("courses")
    average_array = [
        {
            "id": course.id,
            "grade": Grade.objects.filter(
                course_id=course.id
            ).aggregate(average=Avg("grade"))["average"],
        }
        for course in Course.objects.all()
    ]
    template = (
        "portal/mobile_grades.html"
        if "mobile" in user_agent
        else "portal/desktop_grades.html"
    )
    return render(request, template, {
        "grades": average_array,
        "profile_photo": profile_photo,
    })

@approved_required
@login_required
def announcements(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    if _is_teacher(request.user):
        announcements = Announcement.objects.all()
    elif request.user.user_type == CustomUser.STUDENT and not request.user.is_superuser:
        courses = Course.objects.filter(people=request.user)
        announcements = Announcement.objects.filter(recipients__in=courses)
    else:
        announcements = Announcement.objects.none()

    return render(request, "portal/announcements.html", {
        "announcements": announcements.distinct().order_by("-created_at").prefetch_related("recipients"),
        "profile_photo": profile_photo,
        "active_nav": "announcements",
    })

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

        students = Course.objects.get(id=course_id).people.all()

        for student in students:
            status = 'Absent'  # Default to absent
            if f'attendance_status_{student.id}' in request.POST:
                status = 'Present'

            # Update or create the attendance record
            Attendance.objects.update_or_create(
                student=student,
                course_id=course_id,
                day=selected_day,
                month=selected_month,
                year=selected_year,
                defaults={'status': status}
            )

        return redirect('attendance', course_id=course_id)
    else:
        all_students = Course.objects.get(id=course_id).people.all()
        course = Course.objects.get(id=course_id)

        # Query attendance records for the given day, month, and year
        attendance_records = Attendance.objects.filter(
            course_id=course_id, day=day, month=month, year=year
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
        user_agent = _user_agent(request)
        if "mobile" in user_agent:
            return render(request, 'portal/mobile_attendanceAdd.html', context)
        else:
            return render(request, 'portal/desktop_attendanceAdd.html', context)

@approved_required
@login_required
def attendance(request: HttpRequest, course_id, year=None, month=None):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = _user_agent(request)
    course = get_object_or_404(Course, id=course_id)
    _require_course_access(request.user, course)
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

    if not request.user.is_superuser and request.user.user_type == CustomUser.STUDENT:
        attendance = Attendance.objects.filter(course=course, year = year, month = month, student = request.user, status = "Present").values_list('day', flat=True)
        attendance_days = list(attendance)
        absent = Attendance.objects.filter(course=course, year = year, month = month, student = request.user, status = "Absent").values_list('day', flat=True)
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
            schedule = Schedule.objects.get(course = Course.objects.get(id = course_id))
        except Exception as e:
            schedule = None
        attendanceForm = UploadedAttendanceForm(course=course)
        if schedule:
            start_date = datetime.strptime(schedule.start_date, "%Y-%m")
            end_date = datetime.strptime(schedule.end_date, "%Y-%m")
            currDate = datetime(year, month, 1)
            if start_date <= currDate <= end_date:
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
    course = get_object_or_404(Course, id=course_id)
    next_url = request.META.get('HTTP_REFERER', '/')
    form = UploadedAttendanceForm(
        request.POST,
        request.FILES,
        course=course,
    )
    print("Submitted data:", form)
    if form.is_valid():
        upload = form.save(commit=False)
        upload.course = course
        upload.save()
    return redirect(next_url)

@approved_required
@teacher_required
@superuser_required
@require_POST
@login_required
def uploadGroupPhoto(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    next_url = request.META.get('HTTP_REFERER', '/')
    form = GroupPhotoUploadForm(request.POST, request.FILES)
    print("Submitted data:", form)
    if form.is_valid():
        upload = form.save(commit=False)
        upload.course = course
        upload.save()
    return redirect(next_url)

@approved_required    
@teacher_required
@superuser_required
@login_required
@require_POST
def scheduleDefine(request, course_id):
    next_url = request.META.get('HTTP_REFERER', '/')
    choices = request.POST.getlist('week')
    start_date = request.POST.get('startDate')
    end_date = request.POST.get('endDate')
    try:
        start = datetime.strptime(start_date or "", "%Y-%m")
        end = datetime.strptime(end_date or "", "%Y-%m")
        weekdays = [int(choice) for choice in choices]
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Invalid schedule values."}, status=400)
    if start > end or any(day not in range(7) for day in weekdays):
        return JsonResponse({"detail": "Invalid schedule range."}, status=400)
    course = get_object_or_404(Course, id=course_id)
    Schedule.objects.update_or_create(
        course=course,
        defaults={
            "start_date": start_date,
            "end_date": end_date,
            "days": json.dumps(weekdays),
        },
    )
    return redirect(next_url)



@login_required
@admin_required
@approved_required
def adminViewHome(request:HttpRequest):
    user_agent = _user_agent(request)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user_type = request.POST.get('user_type')
        user = get_object_or_404(CustomUser, id=user_id)
        valid_roles = {value for value, _ in CustomUser.USER_TYPES}
        if user_type not in valid_roles:
            raise ValidationError("Invalid user role.")
        user.user_type = user_type
        user.is_superuser = user_type in (
            CustomUser.TEACHER,
            CustomUser.ADMIN,
        )
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
        send_mail(
            subject,
            plain_text_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=message,
        )
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
    user_agent = _user_agent(request)
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
        user = get_object_or_404(CustomUser, id=user_id)
        if user == request.user:
            return JsonResponse(
                {"detail": "You cannot delete your own account."},
                status=400,
            )
        if (
            user.user_type == CustomUser.ADMIN
            and CustomUser.objects.filter(
                user_type=CustomUser.ADMIN,
                approved=True,
                is_active=True,
            ).count() <= 1
        ):
            return JsonResponse(
                {"detail": "The last active administrator cannot be deleted."},
                status=400,
            )
        user.delete()
        return redirect('adminUsers')

@require_POST
@login_required
@admin_required
@approved_required
def admit_user(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(CustomUser, id=user_id)
        if user == request.user:
            return JsonResponse(
                {"detail": "You cannot revoke your own approval."},
                status=400,
            )
        if (
            user.user_type == CustomUser.ADMIN
            and CustomUser.objects.filter(
                user_type=CustomUser.ADMIN,
                approved=True,
                is_active=True,
            ).count() <= 1
        ):
            return JsonResponse(
                {"detail": "The last active administrator cannot be revoked."},
                status=400,
            )
        user.approved = False
        user.save()
        return redirect('adminViewHome')


@require_POST
@teacher_required
@superuser_required
@login_required
@approved_required
def deleteCourse(request, course_id):
    if request.method == 'POST':
        course = get_object_or_404(Course, id=course_id)
        with transaction.atomic():
            sections = list(Section.objects.filter(course_id=course_id))
            folders = {
                folder.id: folder
                for section in sections
                for folder in section.folders.all()
            }
            assignments = {
                assignment.id: assignment
                for folder in folders.values()
                for assignment in folder.assignments.all()
            }
            for section in sections:
                section.delete()
            for folder in folders.values():
                if not folder.section_set.exists():
                    folder.delete()
            for assignment in assignments.values():
                if not assignment.folder_set.exists():
                    assignment.delete()
            Grade.objects.filter(course_id=course_id).delete()
            course.delete()
        return redirect("courses")

@require_POST
@teacher_required
@superuser_required
@login_required
@approved_required
def deleteSection(request, section_id):
    section = get_object_or_404(Section, id=section_id)
    course_id = section.course_id
    section_order_num = section.order
    folders = list(section.folders.all())
    assignments = {
        assignment.id: assignment
        for folder in folders
        for assignment in folder.assignments.all()
    }
    with transaction.atomic():
        section.delete()
        for folder in folders:
            if not folder.section_set.exists():
                folder.delete()
        for assignment in assignments.values():
            if not assignment.folder_set.exists():
                assignment.delete()
    remaining_sections = Section.objects.filter(course_id=course_id).order_by('order')
    for idx, sec in enumerate(remaining_sections):
        if sec.order > section_order_num:
            sec.order = sec.order - 1
            sec.save()
    return redirect("course", course_id)

@login_required
@admin_required
@approved_required
def adminContactView(request:HttpRequest):
    contacts = Contact.objects.filter(is_spam = False)
    user_agent = _user_agent(request)
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
        messages.success(request, "Your profile photo was updated.")
    else:
        messages.error(
            request,
            "The profile photo could not be uploaded. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )

    if course_id:
        return redirect('profile', course_id=course_id)
    return redirect('profile')

@approved_required
@login_required
@require_POST
def signout(request):
    logout(request) 
    return redirect('login')

@approved_required
@login_required
def profile(request: HttpRequest, course_id=None):
    if course_id:
        course = get_object_or_404(Course, id=course_id)
        _require_course_access(request.user, course)
    else:
        course = None
    user = request.user
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    form = ProfilePhotoForm()
    return render(request, "portal/profile.html", {
        "course": course,
        "user": user,
        "form": form,
        "profile_photo": profile_photo,
        "active_nav": "profile",
    })

def send_announcement_emails(announcement):
    recipients = set()
    all_sent = True
    for course in announcement.recipients.all():
        students = course.people.filter(user_type=CustomUser.STUDENT).distinct()
        for student in students:
            if student.email not in recipients:
                print(f"Sending email to: {student.email}")
                recipients.add(student.email)
                try:
                    send_mail(
                        subject=f'New Announcement: {announcement.title}',
                        message=announcement.content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[student.email],
                        fail_silently=False,
                    )
                    print(f"Email sent to: {student.email}")
                except Exception as e:
                    all_sent = False
                    print(f"Failed to send email to: {student.email}, error: {e}")
    announcement.sent = all_sent
    announcement.save(update_fields=['sent'])

@approved_required
@teacher_required
@superuser_required
@login_required
def create_announcement(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()    
    user_agent = _user_agent(request)
    if request.method == 'POST':
        print("Form submitted")
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            print("Form is valid")
            announcement = form.save()

            send_announcement_emails(announcement)

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
    user_agent = _user_agent(request)
    gradeArray = []
    Course, _, _, _ = _course_graph(
        folder_id=folder_id,
        assignment_id=assignment_id,
    )
    course_id = Course.id
    for people in Course.people.all():
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
                    grade_value = _parse_grade(grade_new)
                except ValidationError:
                    continue
                Grade.objects.update_or_create(
                    assignment_id=assignment_id,
                    course_id=course_id,
                    user_id=people['id'],
                    defaults={"grade": grade_value},
                )
        return redirect("gradesforAssignment", folder_id, assignment_id)
    if "mobile" in user_agent:    
        return render(request, "portal/mobile_gradeStudents.html", {"grades":gradeArray, "course":Course, "profile_photo":profile_photo})
    else:
        return render(request, "portal/desktop_gradeStudents.html", {"grades":gradeArray, "course":Course, "profile_photo":profile_photo})

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def removeStudentFromCourse(request, course_id):
    id = request.POST.get("student_id")
    course = get_object_or_404(Course, id=course_id)
    student = get_object_or_404(
        course.people,
        id=id,
        user_type=CustomUser.STUDENT,
    )
    course.people.remove(student)
    return redirect("students", course.id)

@approved_required
@teacher_required
@superuser_required
@login_required
def submissions(request: HttpRequest, folder_id, user_id, assignment_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = _user_agent(request)
    course, _, folder, assignment = _course_graph(
        folder_id=folder_id,
        assignment_id=assignment_id,
    )
    if not course.people.filter(id=user_id, user_type=CustomUser.STUDENT).exists():
        raise Http404
    grade = Grade.objects.filter(
        user_id=user_id,
        assignment_id=assignment_id,
        course_id=course.id,
    ).first()
    submissions = Submission.objects.filter(user_id =user_id, assignment_id = assignment_id)
    user = CustomUser.objects.get(id = user_id)
    if "mobile" in user_agent:
        return render(request, "portal/mobile_submissionView.html", context = {"submissions":submissions, "grade":grade, "folder":folder, "user": user, "assignment":assignment, "profile_photo":profile_photo})
    else:
        return render(request, "portal/desktop_submissionView.html", context = {"submissions":submissions, "grade":grade, "folder":folder, "user": user, "assignment":assignment, "profile_photo":profile_photo})

def PasswordResetView(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = CustomUser.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            current_site = get_current_site(request)
            subject = 'Reset Your Password'
            message = render_to_string('email/resetPassword.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
                'protocol': 'https' if request.is_secure() else 'http',
            })
            send_mail(
                subject,
                '',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=message,
            )
        return redirect('login')
    return render(request, 'portal/passwordResetInitial.html')

@approved_required
@teacher_required
@superuser_required
@login_required
@require_POST
def upload_syllabus(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    form = SyllabusUploadForm(request.POST, request.FILES, instance=course)
    if form.is_valid():
        if course.syllabus and os.path.exists(course.syllabus.path):
            os.remove(course.syllabus.path)
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
                try:
                    validate_password(password1, user=user)
                except ValidationError as error:
                    return render(
                        request,
                        'portal/passwordReset.html',
                        {'errors': error.messages},
                    )
                user.set_password(password1)
                user.save()
                return redirect('login')
            return render(
                request,
                'portal/passwordReset.html',
                {'errors': ['Passwords do not match.']},
            )
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
            phone = validate_phone_number(phone)
            if CustomUser.objects.filter(email=email).exists():
                return redirect('login')
        except ValidationError as e:
            return render(request, "registration.html", {"error": str(e)})
        if firstname and lastname and email and password and phone:
            try:
                validate_password(password)
            except ValidationError as error:
                return render(request, "registration.html", {"error": " ".join(error.messages)})
            user = CustomUser.objects.create_user(
                first_name=firstname,
                last_name=lastname,
                phone_number=phone,
                username=email,
                email=email,
                password=password,
                is_active=False,
            )
            current_site = get_current_site(request)
            subject = 'Activate Your Account'
            message = render_to_string('email/activation.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
                'protocol': 'https' if request.is_secure() else 'http',
            })
            send_mail(
                subject,
                '',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=message,
            )
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
    Course.objects.create(title = title, description = description)
    return redirect("courses")

@teacher_required
@superuser_required
@login_required
@require_POST
def sectionAdd(request, course_id):
    user = request.user
    course = Course.objects.get(id = course_id)
    title = request.POST.get('title')
    Count = Section.objects.filter(course_id = course_id).count()
    if Count is None:
            Count = 0
    Section.objects.create(title = title, course_id = course_id, order = Count)
    return redirect("course", course_id)

@teacher_required
@superuser_required
@login_required
def addStudents(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = Course.objects.get(id=course_id)
    enrolled_students = course.people.all()
    all_students = CustomUser.objects.filter(
        user_type=CustomUser.STUDENT
    ).exclude(id__in=enrolled_students)
    if request.method == 'POST':
        selected_students = request.POST.getlist('selected_students')
        for student_id in selected_students:
            student = CustomUser.objects.get(id=student_id)
            course.people.add(student)
        return redirect('students', course.id)
    else:
        context = {
            'course': course,
            'all_students': all_students,
            'profile_photo':profile_photo
        }
    user_agent = _user_agent(request)
    if "mobile" in user_agent:
        return render(request, "portal/mobile_studentAdd.html", context)
    else:
        return render(request, "portal/desktop_studentAdd.html", context)

def account_activation_sent(request):
    return render(request, 'portal/invalidAccountActivation.html')

@require_POST
@login_required
@approved_required
@emailSender_required
def addKirtan(request):
    date = datetime.strptime(request.POST.get("kirtanDate"), "%Y-%m-%d")
    hostingFamily = request.POST.get("hostingFamily")
    WeeklyEmail.objects.create(email_type = "weekly", organizer = hostingFamily, date_created = datetime.today(), date_scheduled= date,  sent=False, subject ="Weekly Kirtan")
    return redirect("calenderNotification")

@login_required
@admin_required
@approved_required
@require_POST
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
    course_id = section.course_id
    title = request.POST.get('title')
    Count = Section.objects.filter(course_id = course_id).count()
    if Count is None:
        Count = 0
    folder = Folder.objects.create(title = title, course_id = course_id)
    section.folders.add(folder)
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

@approved_required
@emailSender_required
@login_required
def calenderNotification(request: HttpRequest, year=None, month=None):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = _user_agent(request)
    
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

@require_POST
@login_required
@approved_required
@emailSender_required
def delete_email(request, email_id):
    email = get_object_or_404(WeeklyEmail, id=email_id)
    email.delete()
    return redirect('calenderNotification')

@login_required
@approved_required
@emailSender_required
def calendarEventView(request: HttpRequest, email_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    user_agent = _user_agent(request)
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
        return redirect("calenderNotification")
