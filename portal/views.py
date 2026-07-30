from django.shortcuts import render, redirect, get_object_or_404
from portal.models import CustomUser, Schedule, WeeklyEmail, Course, Section, Folder, Grade, Announcement, Attendance, CarouselImage
from django.http import HttpRequest, JsonResponse, FileResponse, Http404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.models import Group
from django.contrib import messages
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives, send_mail
from main.models import BlacklistedIP
from django.http import HttpResponse
from django.contrib.auth.tokens import default_token_generator
from .forms import UploadedFileForm, FileUploadForm, AnnouncementForm,UploadedAttendanceForm,GroupPhotoUploadForm, ProfilePhotoForm, CarouselImageForm, SyllabusUploadForm
from .models import UploadedFile, Assignment, Submission
from main.models import CarouselImage as Carousel
from main.forms import CarouselImageForm as MainCarouselImageForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.validators import UnicodeUsernameValidator
from .decorators import (
    teacher_required,
    admin_required,
    approved_required,
    emailSender_required,
    web_manager_required,
)
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from asgiref.sync import sync_to_async
from pages.forms import MailComposeForm
from pages.mailbox import mailbox_is_configured
from pages.models import (
    ActivationEmailDelivery,
    Contact,
    MailboxMessage,
    MailDraft,
    TwoFactorEmailDelivery,
)
from pages.tasks import two_factor_code_for_nonce
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.db.models import Avg, Q
import re
import os
import asyncio
import calendar
from datetime import datetime, timedelta
import json
import logging
import mimetypes
import secrets


logger = logging.getLogger(__name__)


TWO_FACTOR_USER_SESSION_KEY = "two_factor_user_id"
TWO_FACTOR_HASH_SESSION_KEY = "two_factor_code_hash"
TWO_FACTOR_EXPIRES_SESSION_KEY = "two_factor_code_expires"
TWO_FACTOR_ATTEMPTS_SESSION_KEY = "two_factor_attempts"
TWO_FACTOR_BACKEND_SESSION_KEY = "two_factor_backend"
TWO_FACTOR_SENT_SESSION_KEY = "two_factor_last_sent"
TWO_FACTOR_SESSION_KEYS = (
    TWO_FACTOR_USER_SESSION_KEY,
    TWO_FACTOR_HASH_SESSION_KEY,
    TWO_FACTOR_EXPIRES_SESSION_KEY,
    TWO_FACTOR_ATTEMPTS_SESSION_KEY,
    TWO_FACTOR_BACKEND_SESSION_KEY,
    TWO_FACTOR_SENT_SESSION_KEY,
)
TWO_FACTOR_CODE_LIFETIME_SECONDS = 10 * 60
TWO_FACTOR_RESEND_COOLDOWN_SECONDS = 60
TWO_FACTOR_MAX_ATTEMPTS = 5


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
    return user.is_teacher


def _students(queryset=None):
    queryset = queryset if queryset is not None else CustomUser.objects.all()
    return queryset.filter(
        Q(user_type=CustomUser.STUDENT) | Q(groups__name=CustomUser.STUDENT)
    ).distinct()


def _can_access_course(user, course):
    return _is_teacher(user) or (
        user.is_student
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
@login_required
def students(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = get_object_or_404(Course, id=course_id)
    students = _students(course.people.all()).order_by(
        "last_name", "first_name", "username"
    )
    return render(request, "portal/students.html", {
        "students": students,
        "profile_photo": profile_photo,
        "course": course,
        "active_nav": "courses",
    })

@approved_required
@login_required
def fileView(request, file_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    file = get_object_or_404(UploadedFile, id=file_id)
    course_ids = set(Folder.objects.filter(files=file).values_list('course_id', flat=True))
    course_ids.update(Folder.objects.filter(
        assignments__files=file
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
@web_manager_required
def carousel_management(request: HttpRequest):
    images = CarouselImage.objects.order_by("order", "id")
    mainImages = Carousel.objects.order_by("order", "id")
    form = CarouselImageForm()
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    mainform = MainCarouselImageForm()
    return render(request, "portal/admin_carousel.html", {
        "profile_photo": profile_photo,
        "images": images,
        "mainImages": mainImages,
        "form": form,
        "mainform": mainform,
        "active_nav": "carousel",
    })

@login_required
@approved_required
@web_manager_required
@require_POST
def mainCarouselImageUpload(request):
    form = MainCarouselImageForm(request.POST, request.FILES)
    if form.is_valid():
        with transaction.atomic():
            items = _normalize_carousel_order(Carousel)
            image = form.save(commit=False)
            image.order = len(items)
            image.save()
        messages.success(request, "The website carousel image was added.")
    else:
        messages.error(
            request,
            "The website carousel image could not be added. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )
    return redirect('carousel_management')

@login_required
@approved_required
@web_manager_required
@require_POST
def gurmukhiSchoolImageUpload(request):
    form = CarouselImageForm(request.POST, request.FILES)
    if form.is_valid():
        with transaction.atomic():
            items = _normalize_carousel_order(CarouselImage)
            image = form.save(commit=False)
            image.order = len(items)
            image.save()
        messages.success(request, "The school carousel image was added.")
    else:
        messages.error(
            request,
            "The school carousel image could not be added. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )
    return redirect('carousel_management')


def _normalize_carousel_order(model):
    items = list(model.objects.select_for_update().order_by("order", "id"))
    changed = []
    for index, item in enumerate(items):
        if item.order != index:
            item.order = index
            changed.append(item)
    if changed:
        model.objects.bulk_update(changed, ["order"])
    return items


def _move_carousel_image(model, image_id, offset):
    with transaction.atomic():
        items = _normalize_carousel_order(model)
        current_index = next(
            (index for index, item in enumerate(items) if item.pk == image_id),
            None,
        )
        if current_index is None:
            raise Http404("Carousel image not found.")
        target_index = current_index + offset
        if not 0 <= target_index < len(items):
            return
        current = items[current_index]
        target = items[target_index]
        current.order, target.order = target.order, current.order
        model.objects.bulk_update([current, target], ["order"])

@login_required
@approved_required
@web_manager_required
@require_POST
def moveMainCarouselImageUp(request, image_id):
    _move_carousel_image(Carousel, image_id, -1)
    return redirect("carousel_management")

@login_required
@approved_required
@web_manager_required
@require_POST
def moveMainCarouselImageDown(request, image_id):
    _move_carousel_image(Carousel, image_id, 1)
    return redirect("carousel_management")

@login_required
@approved_required
@web_manager_required
@require_POST
def moveCarouselImageUp(request, image_id):
    _move_carousel_image(CarouselImage, image_id, -1)
    return redirect("carousel_management")

@login_required
@approved_required
@web_manager_required
@require_POST
def moveCarouselImageDown(request, image_id):
    _move_carousel_image(CarouselImage, image_id, 1)
    return redirect("carousel_management")

@require_POST
@login_required
@approved_required
@admin_required
def contactSpam(request, contact_id):
    contact = get_object_or_404(Contact, id=contact_id)
    Contact.objects.filter(pk=contact.pk).update(
        is_spam=True,
        spam_reviewed=True,
    )
    messages.success(request, f"The message from {contact.name} was marked as spam.")
    return redirect("adminContactView")


@require_POST
@login_required
@approved_required
@admin_required
def contactRestore(request, contact_id):
    contact = get_object_or_404(Contact, id=contact_id)
    Contact.objects.filter(pk=contact.pk).update(
        is_spam=False,
        spam_reviewed=True,
    )
    messages.success(request, f"The message from {contact.name} was restored to the inbox.")
    return redirect("adminContactView")


@require_POST
@login_required
@approved_required
@admin_required
def contactTrust(request, contact_id):
    contact = get_object_or_404(Contact, id=contact_id, is_spam=False)
    Contact.objects.filter(pk=contact.pk).update(spam_reviewed=True)
    messages.success(
        request,
        f"The message from {contact.name} was trusted as legitimate.",
    )
    return redirect("adminContactView")


@require_POST
@login_required
@approved_required
@admin_required
def mailboxSpam(request, message_id):
    mailbox_message = get_object_or_404(MailboxMessage, id=message_id)
    MailboxMessage.objects.filter(pk=mailbox_message.pk).update(
        is_spam=True,
        spam_reviewed=True,
    )
    messages.success(request, "The email was marked as spam.")
    return redirect("adminContactView")


@require_POST
@login_required
@approved_required
@admin_required
def mailboxRestore(request, message_id):
    mailbox_message = get_object_or_404(MailboxMessage, id=message_id)
    MailboxMessage.objects.filter(pk=mailbox_message.pk).update(
        is_spam=False,
        spam_reviewed=True,
    )
    messages.success(request, "The email was restored to the inbox.")
    return redirect("adminContactView")


@require_POST
@login_required
@approved_required
@admin_required
def mailboxTrust(request, message_id):
    mailbox_message = get_object_or_404(
        MailboxMessage,
        id=message_id,
        is_spam=False,
    )
    MailboxMessage.objects.filter(pk=mailbox_message.pk).update(
        spam_reviewed=True,
    )
    messages.success(request, "The email was trusted as legitimate.")
    return redirect("adminContactView")
    
@require_POST
@login_required
@approved_required
@admin_required
def contactDelete(request, contact_id):
    contact = get_object_or_404(Contact, id=contact_id)
    sender_name = contact.name
    contact.delete()
    messages.success(request, f"The message from {sender_name} was deleted.")
    return redirect("adminContactView")

@require_POST
@login_required
@approved_required
@web_manager_required
def delete_carousel_image(request):
    image = get_object_or_404(CarouselImage, id=request.POST.get('image_id'))
    title = image.title
    storage = image.image.storage
    image_name = image.image.name
    with transaction.atomic():
        image.delete()
        for order, remaining in enumerate(CarouselImage.objects.order_by('order', 'id')):
            if remaining.order != order:
                remaining.order = order
                remaining.save(update_fields=['order'])
    try:
        if image_name:
            storage.delete(image_name)
    except Exception:
        messages.warning(request, f"{title} was removed, but its stored image file could not be deleted.")
    else:
        messages.success(request, f"{title} was removed from the school carousel.")
    return redirect('carousel_management')
    
@require_POST
@login_required
@approved_required
@web_manager_required
def delete_main_carousel_image(request):
    image = get_object_or_404(Carousel, id=request.POST.get('main_image_id'))
    title = image.title
    storage = image.image.storage
    image_name = image.image.name
    with transaction.atomic():
        image.delete()
        for order, remaining in enumerate(Carousel.objects.order_by('order', 'id')):
            if remaining.order != order:
                remaining.order = order
                remaining.save(update_fields=['order'])
    try:
        if image_name:
            storage.delete(image_name)
    except Exception:
        messages.warning(request, f"{title} was removed, but its stored image file could not be deleted.")
    else:
        messages.success(request, f"{title} was removed from the website carousel.")
    return redirect('carousel_management')

@approved_required
@teacher_required
@require_POST
@login_required
def addNewFilesToAssignment(request, section_id, folder_id, assignment_id):
    _course_graph(section_id, folder_id, assignment_id)
    form = UploadedFileForm(request.POST, request.FILES)
    if form.is_valid():
        file = form.save()
        assignment = Assignment.objects.get(id=assignment_id)
        assignment.files.add(file)
        messages.success(request, "The assignment file was attached.")
    else:
        messages.error(
            request,
            "The file could not be attached. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )
    return redirect("viewAssignment", section_id, folder_id, assignment_id)

@approved_required
@require_POST
@login_required
def submitFilesToAssignment(request, section_id, folder_id, assignment_id):
    course, _, _, _ = _course_graph(section_id, folder_id, assignment_id)
    _require_course_access(request.user, course)
    if not request.user.is_student or request.user.is_teacher:
        raise PermissionDenied
    form = FileUploadForm(
        request.POST,
        request.FILES,
        user_id=request.user.id,
        assignment_id=assignment_id,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Your work was submitted.")
    else:
        messages.error(
            request,
            "Your work could not be submitted. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )
    return redirect("viewAssignment", section_id, folder_id, assignment_id)

@approved_required
@teacher_required
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
    course, section, folder, assignment = _course_graph(section_id, folder_id, assignment_id)
    _require_course_access(request.user, course)
    if not _is_teacher(request.user) and not section.status:
        raise PermissionDenied
    files = UploadedFile.objects.exclude(
        id__in=assignment.files.values_list("id", flat=True),
    )
    form = UploadedFileForm()
    studentform = FileUploadForm(user_id = request.user.id, assignment_id = assignment_id)
    profile_photo = request.user.profile_photos.order_by("-uploaded_at").first()
    context = {
        "course": course,
        "section": section,
        "assignment": assignment,
        "folder": folder,
        "form": form,
        "studentform": studentform,
        "files": files,
        "section_id": section_id,
        "folder_id": folder_id,
        "profile_photo": profile_photo,
        "active_nav": "courses",
    }
    if request.user.is_student and not request.user.is_teacher:
        context["submissions"] = Submission.objects.filter(
            user_id=request.user.id,
            assignment_id=assignment_id,
        ).order_by("-date", "-id")
    elif _is_teacher(request.user):
        context["users"] = CustomUser.objects.filter(
            id__in=Submission.objects.filter(
                assignment_id=assignment.id,
            ).values("user_id"),
        ).distinct().order_by("last_name", "first_name")
    return render(request, "portal/assignment.html", context=context)

@approved_required
@teacher_required
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
        assignments__files=file
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
    folders = Folder.objects.filter(assignments__id=submission.assignment_id)
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
    if user.is_teacher:
        courses = Course.objects.all().order_by("title")
    elif user.is_student:
        courses = Course.objects.filter(people=request.user).order_by("title")
    elif user.is_admin:
        return redirect("adminViewHome")
    elif user.is_email_sender:
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
    if not _students(course.people.filter(id=user_id)).exists():
        raise Http404
    try:
        new_grade = _parse_grade(request.POST.get("grade"))
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("submissions", folder_id, user_id, assignment_id)
    Grade.objects.update_or_create(
        user_id=user_id,
        assignment_id=assignment_id,
        course_id=course_id,
        defaults={"grade": new_grade},
    )
    messages.success(request, "The grade was saved.")
    return redirect("submissions", folder_id, user_id, assignment_id)

@approved_required
@login_required
def grades(request: HttpRequest, course_id = None):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    if course_id is not None:
        course = get_object_or_404(Course, id=course_id)
        _require_course_access(request.user, course)
        grade_array = []
        if request.user.is_student and not request.user.is_teacher:
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
            ).values_list('assignments__id', flat=True)
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
                for assignment in assignments.order_by("title")
                if assignment.id in averages
            ]

        grade_array.sort(key=lambda item: item["title"].casefold())
        final = (
            sum(item["grade"] for item in grade_array) / len(grade_array)
            if grade_array else None
        )
        return render(request, "portal/grades.html", {
            "grades": grade_array,
            "course": course,
            "final": final,
            "profile_photo": profile_photo,
            "active_nav": "courses",
        })

    if not _is_teacher(request.user):
        return redirect("courses")
    average_array = [
        {"id": item.id, "title": item.title, "grade": item.average_grade}
        for item in Course.objects.annotate(
            average_grade=Avg("grades__grade"),
        ).order_by("title")
        if item.average_grade is not None
    ]
    overall = (
        sum(item["grade"] for item in average_array) / len(average_array)
        if average_array else None
    )
    return render(request, "portal/grades.html", {
        "grades": average_array,
        "final": overall,
        "profile_photo": profile_photo,
        "active_nav": "courses",
    })

@approved_required
@login_required
def announcements(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    if _is_teacher(request.user):
        announcements = Announcement.objects.all()
    elif request.user.is_student:
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
@login_required
def mark_attendance(request: HttpRequest, course_id, day, month, year):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = get_object_or_404(Course, id=course_id)
    try:
        attendance_date = datetime(year, month, day)
    except ValueError:
        raise Http404
    students = _students(course.people.all()).order_by(
        "last_name", "first_name", "username"
    )
    if request.method == 'POST':
        with transaction.atomic():
            for student in students:
                status = (
                    "Present"
                    if f"attendance_status_{student.id}" in request.POST
                    else "Absent"
                )
                Attendance.objects.update_or_create(
                    student=student,
                    course=course,
                    day=day,
                    month=month,
                    year=year,
                    defaults={"status": status},
                )
        messages.success(request, f"Attendance for {attendance_date:%B %d, %Y} was saved.")
        return redirect("attendance", course_id, year, month)

    present_student_ids = set(Attendance.objects.filter(
        course=course,
        day=day,
        month=month,
        year=year,
        status="Present",
    ).values_list("student_id", flat=True))
    return render(request, "portal/attendance_mark.html", {
        "course": course,
        "all_students": students,
        "day": day,
        "month": month,
        "year": year,
        "attendance_date": attendance_date,
        "attendance_dict": present_student_ids,
        "profile_photo": profile_photo,
        "active_nav": "courses",
    })

@approved_required
@login_required
def attendance(request: HttpRequest, course_id, year=None, month=None):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = get_object_or_404(Course, id=course_id)
    _require_course_access(request.user, course)
    now = datetime.now()
    if not year or not month:
        year = now.year
        month = now.month
    cal = calendar.Calendar()
    month_days = list(cal.itermonthdays2(year, month))
    today = now.day if year == now.year and month == now.month else None
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

    if request.user.is_student and not request.user.is_teacher:
        attendance = Attendance.objects.filter(course=course, year = year, month = month, student = request.user, status = "Present").values_list('day', flat=True)
        attendance_days = list(attendance)
        absent = Attendance.objects.filter(course=course, year = year, month = month, student = request.user, status = "Absent").values_list('day', flat=True)
        absent_days = list(absent)
        context = {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
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
        schedule = Schedule.objects.filter(course=course).first()
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
        'month_name': calendar.month_name[month],
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
    context["active_nav"] = "courses"
    return render(request, "portal/attendance.html", context)

@approved_required
@teacher_required
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
    if form.is_valid():
        upload = form.save(commit=False)
        upload.course = course
        upload.save()
        messages.success(request, "The attendance file was uploaded.")
    else:
        messages.error(
            request,
            "The attendance file could not be uploaded. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )
    return redirect(next_url)

@approved_required
@teacher_required
@require_POST
@login_required
def uploadGroupPhoto(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    next_url = request.META.get('HTTP_REFERER', '/')
    form = GroupPhotoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        upload = form.save(commit=False)
        upload.course = course
        upload.save()
        messages.success(request, "The attendance photos were uploaded.")
    else:
        messages.error(
            request,
            "The photos could not be uploaded. "
            + " ".join(str(error) for errors in form.errors.values() for error in errors),
        )
    return redirect(next_url)

@approved_required    
@teacher_required
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
        messages.error(request, "Enter valid schedule values.")
        return redirect(next_url)
    if start > end or not weekdays or any(day not in range(7) for day in weekdays):
        messages.error(request, "Choose a valid date range and at least one class day.")
        return redirect(next_url)
    course = get_object_or_404(Course, id=course_id)
    Schedule.objects.update_or_create(
        course=course,
        defaults={
            "start_date": start_date,
            "end_date": end_date,
            "days": json.dumps(weekdays),
        },
    )
    messages.success(request, "The attendance schedule was saved.")
    return redirect(next_url)



ROLE_PRIMARY_PRIORITY = (
    CustomUser.TEACHER,
    CustomUser.STUDENT,
    CustomUser.ADMIN,
    CustomUser.EMAIL_SENDER,
    CustomUser.WEB_MANAGER,
    CustomUser.PARENT,
)


def _validated_roles(request):
    roles = set(request.POST.getlist("roles"))
    # Accept the legacy single-select field during a rolling deployment.
    legacy_role = request.POST.get("user_type")
    if legacy_role:
        roles.add(legacy_role)
    if not roles or not roles.issubset(CustomUser.ROLE_VALUES):
        return None, "Select at least one valid user role."
    role_error = CustomUser.role_validation_error(roles)
    if role_error:
        return None, role_error
    return roles, None


def _set_user_roles(user, roles):
    role_error = CustomUser.role_validation_error(roles)
    if role_error:
        raise ValidationError(role_error)
    role_groups = {
        group.name: group
        for group in Group.objects.filter(name__in=CustomUser.ROLE_VALUES)
    }
    missing = CustomUser.ROLE_VALUES.difference(role_groups)
    for role in missing:
        role_groups[role] = Group.objects.create(name=role)
    existing_role_groups = user.groups.filter(name__in=CustomUser.ROLE_VALUES)
    user.groups.remove(*existing_role_groups)
    user.groups.add(*(role_groups[role] for role in roles))
    user.user_type = next(role for role in ROLE_PRIMARY_PRIORITY if role in roles)
    if CustomUser.ADMIN not in roles:
        user.is_superuser = False
        user.is_staff = False
    user.__dict__.pop("role_names", None)


@login_required
@admin_required
@approved_required
def adminViewHome(request:HttpRequest):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(CustomUser, id=user_id, approved=False)
        roles, role_error = _validated_roles(request)
        if roles is None:
            messages.error(request, role_error)
            return redirect("adminViewHome")
        _set_user_roles(user, roles)
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
        if not user.email:
            messages.warning(
                request,
                "The account was approved, but no notification was sent because it has no email address.",
            )
        else:
            try:
                send_mail(
                    subject,
                    plain_text_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=message,
                )
            except Exception:
                messages.warning(request, "The account was approved, but the notification email failed.")
            else:
                messages.success(request, "The account was approved and the user was notified.")
        return redirect("adminViewHome")
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    users = CustomUser.objects.filter(approved=False).select_related(
        "activation_email_delivery"
    ).order_by("date_joined", "id")
    return render(request, "portal/admin_dashboard.html", {
        "users": users,
        "user_roles": CustomUser.USER_TYPES,
        "profile_photo": profile_photo,
        "active_nav": "admin_dashboard",
    })

@login_required
@admin_required
@approved_required
def adminUsers(request:HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    users = CustomUser.objects.filter(approved=True).prefetch_related("groups").order_by(
        "user_type",
        "last_name",
        "first_name",
        "username",
    )
    query = request.GET.get("q", "").strip()
    selected_role = request.GET.get("role", "").strip()
    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
            | Q(email__icontains=query)
        )
    valid_roles = {value for value, _ in CustomUser.USER_TYPES}
    if selected_role in valid_roles:
        users = users.filter(
            Q(groups__name=selected_role) | Q(user_type=selected_role)
        ).distinct()
    else:
        selected_role = ""
    return render(request, "portal/admin_users.html", {
        "users": users,
        "query": query,
        "selected_role": selected_role,
        "user_roles": CustomUser.USER_TYPES,
        "profile_photo": profile_photo,
        "active_nav": "admin_users",
    })


@require_POST
@login_required
@admin_required
@approved_required
def change_user_roles(request):
    user = get_object_or_404(
        CustomUser,
        id=request.POST.get("user_id"),
        approved=True,
    )
    if user == request.user:
        messages.error(request, "You cannot change your own roles.")
        return redirect("adminUsers")
    roles, role_error = _validated_roles(request)
    if roles is None:
        messages.error(request, role_error)
        return redirect("adminUsers")
    if user.is_admin and CustomUser.objects.filter(
        approved=True,
        is_active=True,
        groups__name=CustomUser.ADMIN,
    ).exclude(pk=user.pk).count() == 0 and CustomUser.ADMIN not in roles:
        messages.error(request, "The last active administrator must keep the Admin role.")
        return redirect("adminUsers")
    _set_user_roles(user, roles)
    user.save(update_fields=["user_type", "is_superuser", "is_staff"])
    messages.success(
        request,
        f"Roles for {user.get_full_name() or user.username} were updated.",
    )
    return redirect("adminUsers")


@require_POST
@login_required
@admin_required
@approved_required
def delete_user(request):
    user = get_object_or_404(CustomUser, id=request.POST.get('user_id'))
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect("adminUsers")
    if (
        user.is_admin
        and user.is_active
        and CustomUser.objects.filter(
            approved=True,
            is_active=True,
        ).filter(
            Q(groups__name=CustomUser.ADMIN) | Q(user_type=CustomUser.ADMIN)
        ).distinct().count() <= 1
    ):
        messages.error(request, "The last active administrator cannot be deleted.")
        return redirect("adminUsers")
    display_name = user.get_full_name() or user.username
    user.delete()
    messages.success(request, f"{display_name} was deleted.")
    return redirect('adminUsers')

@require_POST
@login_required
@admin_required
@approved_required
def admit_user(request):
    user = get_object_or_404(
        CustomUser,
        id=request.POST.get('user_id'),
        approved=True,
    )
    if user == request.user:
        messages.error(request, "You cannot move your own account to the waitlist.")
        return redirect("adminUsers")
    if (
        user.is_admin
        and user.is_active
        and CustomUser.objects.filter(
            approved=True,
            is_active=True,
        ).filter(
            Q(groups__name=CustomUser.ADMIN) | Q(user_type=CustomUser.ADMIN)
        ).distinct().count() <= 1
    ):
        messages.error(request, "The last active administrator cannot be moved to the waitlist.")
        return redirect("adminUsers")
    display_name = user.get_full_name() or user.username
    user.approved = False
    user.is_active = False
    user.save(update_fields=["approved", "is_active"])
    messages.success(request, f"{display_name} was moved to the account waitlist.")
    return redirect('adminViewHome')


@require_POST
@teacher_required
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
    status = request.GET.get("status", "inbox")
    query = request.GET.get("q", "").strip()
    selected_date = request.GET.get("date", "").strip()
    contacts = Contact.objects.none()
    mailbox_messages = MailboxMessage.objects.none()
    drafts = MailDraft.objects.none()
    if status == "spam":
        contacts = Contact.objects.filter(is_spam=True)
        mailbox_messages = MailboxMessage.objects.filter(is_spam=True)
    elif status == "contact":
        contacts = Contact.objects.filter(is_spam=False)
    elif status == "email":
        mailbox_messages = MailboxMessage.objects.filter(is_spam=False)
    elif status == "drafts":
        drafts = MailDraft.objects.filter(
            status__in=[MailDraft.DRAFT, MailDraft.QUEUED]
        )
    elif status == "sent":
        drafts = MailDraft.objects.filter(status=MailDraft.SENT)
    else:
        status = "inbox"
        contacts = Contact.objects.filter(is_spam=False)
        mailbox_messages = MailboxMessage.objects.filter(is_spam=False)
    if query:
        contacts = contacts.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(message__icontains=query)
        )
        mailbox_messages = mailbox_messages.filter(
            Q(sender_name__icontains=query)
            | Q(sender_email__icontains=query)
            | Q(subject__icontains=query)
            | Q(body__icontains=query)
        )
        drafts = drafts.filter(
            Q(recipient__icontains=query)
            | Q(subject__icontains=query)
            | Q(body__icontains=query)
        )
    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            selected_date = ""
        else:
            contacts = contacts.filter(date=filter_date)
            mailbox_messages = mailbox_messages.filter(received_at__date=filter_date)
            drafts = drafts.filter(updated_at__date=filter_date)
    contacts = contacts.order_by("-date", "-id")
    mailbox_messages = mailbox_messages.order_by("-received_at", "-id")
    drafts = drafts.order_by("-updated_at", "-id")
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    return render(request, "portal/admin_contact.html", {
        "contacts": contacts,
        "mailbox_messages": mailbox_messages,
        "drafts": drafts,
        "shown_count": contacts.count() + mailbox_messages.count() + drafts.count(),
        "mailbox_configured": mailbox_is_configured(),
        "profile_photo": profile_photo,
        "status": status,
        "query": query,
        "selected_date": selected_date,
        "active_nav": "admin_contact",
    })


@require_POST
@login_required
@admin_required
@approved_required
def adminMailboxSync(request):
    messages.success(
        request,
        "Mailbox synchronization has been requested and will run with the next background email task.",
    )
    return redirect("adminContactView")


@login_required
@admin_required
@approved_required
def adminMailboxCompose(request):
    draft = None
    draft_id = request.POST.get("draft_id") or request.GET.get("draft")
    if draft_id:
        draft = get_object_or_404(MailDraft, id=draft_id, status=MailDraft.DRAFT)

    contact_id = request.POST.get("contact_id") or request.GET.get("contact")
    message_id = request.POST.get("message_id") or request.GET.get("message")
    contact = (
        get_object_or_404(Contact, id=contact_id)
        if contact_id
        else draft.contact if draft else None
    )
    mailbox_message = (
        get_object_or_404(MailboxMessage, id=message_id)
        if message_id
        else draft.reply_to_message if draft else None
    )
    initial = {}
    if contact:
        initial = {"recipient": contact.email, "subject": ""}
    elif mailbox_message:
        subject = mailbox_message.subject or ""
        initial = {
            "recipient": mailbox_message.sender_email,
            "subject": subject if subject.lower().startswith("re:") else f"Re: {subject}",
        }

    form = MailComposeForm(
        request.POST or None,
        instance=draft,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        mail_record = form.save(commit=False)
        mail_record.created_by = draft.created_by if draft else request.user
        mail_record.created_by_name = (
            draft.created_by_name
            if draft and draft.created_by_name
            else request.user.get_full_name() or request.user.username
        )
        mail_record.contact = contact
        mail_record.reply_to_message = mailbox_message
        action = request.POST.get("action")
        if action == "save":
            mail_record.status = MailDraft.DRAFT
            mail_record.save()
            messages.success(request, "Draft saved.")
            return redirect("adminContactView")
        if action == "send":
            mail_record.status = MailDraft.QUEUED
            mail_record.save()
            messages.success(
                request,
                f"Email queued to send from {settings.DEFAULT_FROM_EMAIL}.",
            )
            return redirect("adminContactView")

    profile_photo = request.user.profile_photos.order_by("-uploaded_at").first()
    return render(
        request,
        "portal/admin_mail_compose.html",
        {
            "form": form,
            "draft": draft,
            "contact": contact,
            "mailbox_message": mailbox_message,
            "profile_photo": profile_photo,
            "active_nav": "admin_contact",
            "from_email": settings.DEFAULT_FROM_EMAIL,
        },
        status=400 if request.method == "POST" and not form.is_valid() else 200,
    )

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


@require_POST
@login_required
@approved_required
@sensitive_post_parameters("password")
def change_username(request):
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    if not request.user.check_password(password):
        messages.error(request, "Your current password is incorrect.")
        return redirect("profile")
    try:
        UnicodeUsernameValidator()(username)
    except ValidationError:
        messages.error(
            request,
            "Use 150 or fewer letters, numbers, or @/./+/-/_ characters.",
        )
        return redirect("profile")
    if not username or len(username) > 150:
        messages.error(
            request,
            "Username must contain between 1 and 150 characters.",
        )
        return redirect("profile")
    if CustomUser.objects.filter(
        username__iexact=username
    ).exclude(pk=request.user.pk).exists():
        messages.error(request, "That username is already in use.")
        return redirect("profile")
    if username == request.user.username:
        messages.info(request, "Your username is already set to that value.")
        return redirect("profile")
    request.user.username = username
    try:
        request.user.save(update_fields=["username"])
    except IntegrityError:
        messages.error(request, "That username is already in use.")
        return redirect("profile")
    messages.success(request, "Your username was updated.")
    return redirect("profile")

def send_announcement_emails(announcement):
    recipients = set()
    all_sent = True
    for course in announcement.recipients.all():
        students = _students(course.people.all()).exclude(email="")
        for student in students:
            if student.email not in recipients:
                recipients.add(student.email)
                try:
                    send_mail(
                        subject=f'New Announcement: {announcement.title}',
                        message=announcement.content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[student.email],
                        fail_silently=False,
                    )
                except Exception:
                    all_sent = False
    announcement.sent = all_sent
    announcement.save(update_fields=['sent'])

@approved_required
@teacher_required
@login_required
def create_announcement(request: HttpRequest):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save()
            send_announcement_emails(announcement)
            if announcement.sent:
                messages.success(request, "The announcement was published and notification emails were sent.")
            else:
                messages.warning(request, "The announcement was published, but one or more notification emails failed.")
            return redirect('announcements')
    else:
        form = AnnouncementForm()
    return render(request, "portal/announcement_create.html", {
        "form": form,
        "profile_photo": profile_photo,
        "active_nav": "announcements",
    })

@approved_required
@teacher_required
@login_required
def gradesforAssignment(request: HttpRequest, folder_id, assignment_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course, _, folder, assignment = _course_graph(
        folder_id=folder_id,
        assignment_id=assignment_id,
    )
    section = Section.objects.filter(folders=folder).order_by("order", "id").first()
    if section is None:
        raise Http404
    students = _students(course.people.all()).order_by(
        "last_name", "first_name", "username"
    )
    existing_grades = {
        grade.user_id: grade.grade
        for grade in Grade.objects.filter(
            assignment=assignment,
            course=course,
            user__in=students,
        )
    }
    grade_array = [
        {
            "id": student.id,
            "name": student.get_full_name() or student.username,
            "email": student.email,
            "grade": existing_grades.get(student.id),
        }
        for student in students
    ]
    if request.method == "POST":
        updates = []
        invalid_names = []
        for student_grade in grade_array:
            raw_grade = request.POST.get(f"grade_{student_grade['id']}", "").strip()
            if not raw_grade:
                continue
            try:
                grade_value = _parse_grade(raw_grade)
            except ValidationError:
                invalid_names.append(student_grade["name"])
            else:
                updates.append((student_grade["id"], grade_value))
        if invalid_names:
            messages.error(
                request,
                "Enter a grade from 0 to 100 for: " + ", ".join(invalid_names),
            )
        else:
            with transaction.atomic():
                for student_id, grade_value in updates:
                    Grade.objects.update_or_create(
                        assignment=assignment,
                        course=course,
                        user_id=student_id,
                        defaults={"grade": grade_value},
                    )
            messages.success(request, f"{len(updates)} grade{'s' if len(updates) != 1 else ''} saved.")
            return redirect("gradesforAssignment", folder_id, assignment_id)
    return render(request, "portal/grades_assignment.html", {
        "grades": grade_array,
        "course": course,
        "section": section,
        "folder": folder,
        "assignment": assignment,
        "profile_photo": profile_photo,
        "active_nav": "courses",
    })

@approved_required
@teacher_required
@login_required
@require_POST
def removeStudentFromCourse(request, course_id):
    id = request.POST.get("student_id")
    course = get_object_or_404(Course, id=course_id)
    student = get_object_or_404(_students(course.people.all()), id=id)
    course.people.remove(student)
    messages.success(
        request,
        f"{student.get_full_name() or student.username} was removed from {course.title}.",
    )
    return redirect("students", course.id)

@approved_required
@teacher_required
@login_required
def submissions(request: HttpRequest, folder_id, user_id, assignment_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course, _, folder, assignment = _course_graph(
        folder_id=folder_id,
        assignment_id=assignment_id,
    )
    section = Section.objects.filter(folders=folder).order_by("order", "id").first()
    if section is None:
        raise Http404
    if not _students(course.people.filter(id=user_id)).exists():
        raise Http404
    grade = Grade.objects.filter(
        user_id=user_id,
        assignment_id=assignment_id,
        course_id=course.id,
    ).first()
    student = get_object_or_404(CustomUser, id=user_id)
    submissions = Submission.objects.filter(
        user_id=user_id,
        assignment_id=assignment_id,
    ).order_by("-date", "-id")
    return render(request, "portal/submissions.html", {
        "submissions": submissions,
        "grade": grade,
        "course": course,
        "section": section,
        "folder": folder,
        "student": student,
        "assignment": assignment,
        "profile_photo": profile_photo,
        "active_nav": "courses",
    })

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
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password')
        phone = request.POST.get('phoneNumber')
        try:
            phone = validate_phone_number(phone)
            UnicodeUsernameValidator()(username)
        except ValidationError as e:
            return render(request, "registration.html", {"error": str(e)})
        if len(username) > 150:
            return render(
                request,
                "registration.html",
                {"error": "Username must be 150 characters or fewer."},
            )
        if CustomUser.objects.filter(username__iexact=username).exists():
            return render(
                request,
                "registration.html",
                {"error": "That username is already in use."},
            )
        if CustomUser.objects.filter(email__iexact=email).exists():
            return render(
                request,
                "registration.html",
                {"error": "An account already uses that email address."},
            )
        if firstname and lastname and username and email and password and phone:
            try:
                validate_password(password)
            except ValidationError as error:
                return render(request, "registration.html", {"error": " ".join(error.messages)})
            current_site = get_current_site(request)
            try:
                with transaction.atomic():
                    user = CustomUser.objects.create_user(
                        first_name=firstname,
                        last_name=lastname,
                        phone_number=phone,
                        username=username,
                        email=email,
                        password=password,
                        is_active=False,
                    )
                    ActivationEmailDelivery.objects.create(
                        user=user,
                        domain=current_site.domain,
                        protocol=(
                            "https" if request.is_secure() else "http"
                        ),
                    )
            except IntegrityError:
                return render(
                    request,
                    "registration.html",
                    {
                        "error": (
                            "That username or email address is already in use."
                        )
                    },
                )
            messages.success(
                request,
                "Registration received. Your activation email has been queued.",
            )
            return redirect('login')
    return render(request,"registration.html")


@sensitive_post_parameters("email")
@never_cache
def resend_activation(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        user = CustomUser.objects.filter(
            email__iexact=email,
            is_active=False,
        ).first()
        if user is not None:
            current_site = get_current_site(request)
            delivery, created = ActivationEmailDelivery.objects.get_or_create(
                user=user,
                defaults={
                    "domain": current_site.domain,
                    "protocol": (
                        "https" if request.is_secure() else "http"
                    ),
                },
            )
            cooldown = settings.ACTIVATION_RESEND_COOLDOWN_SECONDS
            elapsed = (
                timezone.now() - delivery.requested_at
            ).total_seconds()
            if created or elapsed >= cooldown:
                delivery.domain = current_site.domain
                delivery.protocol = (
                    "https" if request.is_secure() else "http"
                )
                delivery.status = ActivationEmailDelivery.QUEUED
                delivery.attempts = 0
                delivery.last_error = ""
                delivery.sent_at = None
                delivery.save(
                    update_fields=[
                        "domain",
                        "protocol",
                        "status",
                        "attempts",
                        "last_error",
                        "sent_at",
                        "requested_at",
                    ]
                )
        messages.success(
            request,
            "If an inactive account uses that email address, a new "
            "activation message will be queued when allowed.",
        )
        return redirect("resend_activation")
    return render(
        request,
        "portal/resend_activation.html",
        {
            "cooldown_minutes": max(
                1,
                settings.ACTIVATION_RESEND_COOLDOWN_SECONDS // 60,
            )
        },
    )

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
@login_required
@require_POST
def courseAdd(request):
    title = request.POST.get('title')
    description = request.POST.get('description')
    Course.objects.create(title = title, description = description)
    return redirect("courses")

@teacher_required
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

@approved_required
@teacher_required
@login_required
def addStudents(request: HttpRequest, course_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    course = get_object_or_404(Course, id=course_id)
    enrolled_student_ids = _students(course.people.all()).values_list("id", flat=True)
    all_students = _students().exclude(id__in=enrolled_student_ids).order_by(
        "last_name",
        "first_name",
        "username",
    )
    if request.method == 'POST':
        selected_students = []
        for value in request.POST.getlist("selected_students"):
            try:
                selected_students.append(int(value))
            except (TypeError, ValueError):
                continue
        students_to_add = all_students.filter(id__in=selected_students)
        added_count = students_to_add.count()
        if added_count:
            course.people.add(*students_to_add)
            messages.success(
                request,
                f"{added_count} student{'s' if added_count != 1 else ''} added to {course.title}.",
            )
        else:
            messages.info(request, "Select at least one available student.")
        return redirect('students', course.id)
    return render(request, "portal/students_add.html", {
        "course": course,
        "all_students": all_students,
        "profile_photo": profile_photo,
        "active_nav": "courses",
    })

def account_activation_sent(request):
    return render(request, 'portal/invalidAccountActivation.html')

@require_POST
@login_required
@approved_required
@emailSender_required
def addKirtan(request):
    date_value = request.POST.get("kirtanDate", "").strip()
    hosting_family = request.POST.get("hostingFamily", "").strip()
    try:
        scheduled_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Select a valid event date.")
        return redirect("calenderNotification")
    if not hosting_family:
        messages.error(request, "Enter the hosting family or organizer.")
        return redirect(
            "calenderNotification",
            scheduled_date.year,
            scheduled_date.month,
        )
    WeeklyEmail.objects.create(
        email_type="weekly",
        organizer=hosting_family,
        date_scheduled=scheduled_date,
        sent=False,
        subject="Weekly Kirtan",
    )
    messages.success(request, "The weekly Kirtan event was scheduled.")
    return redirect(
        "calenderNotification",
        scheduled_date.year,
        scheduled_date.month,
    )

@login_required
@admin_required
@approved_required
@require_POST
def changeUserInfo(request):
    user = get_object_or_404(
        CustomUser,
        id=request.POST.get("user_id"),
        approved=True,
    )
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    if not first_name or not last_name:
        messages.error(request, "First and last name are required.")
        return redirect("adminUsers")
    user.first_name = first_name
    user.last_name = last_name
    user.save(update_fields=["first_name", "last_name"])
    messages.success(request, f"{user.get_full_name()} was updated.")
    return redirect("adminUsers")


@require_POST
@login_required
@admin_required
@approved_required
def changeContactNotifications(request):
    user = get_object_or_404(
        CustomUser,
        id=request.POST.get("user_id"),
        approved=True,
    )
    display_name = user.get_full_name() or user.username
    if user.is_admin:
        messages.info(
            request,
            f"{display_name} is an administrator and already receives contact notifications.",
        )
        return redirect("adminUsers")
    enabled = request.POST.get("enabled") == "true"
    user.contact_notifications_enabled = enabled
    user.save(update_fields=["contact_notifications_enabled"])
    if enabled:
        messages.success(request, f"{display_name} will receive new contact-message emails.")
    else:
        messages.success(request, f"{display_name} will no longer receive contact-message emails.")
    return redirect("adminUsers")

@teacher_required
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


def _clear_two_factor_session(request):
    for key in TWO_FACTOR_SESSION_KEYS:
        request.session.pop(key, None)


def _portal_home_for_user(user):
    if user.is_teacher or user.is_student:
        return "courses"
    if user.is_admin:
        return "adminViewHome"
    if user.is_email_sender:
        return "calenderNotification"
    if user.is_web_manager:
        return "carousel_management"
    return "profile"


def _send_two_factor_code(request, user, backend=None):
    nonce = secrets.token_urlsafe(32)
    code = two_factor_code_for_nonce(nonce)
    now_timestamp = int(timezone.now().timestamp())
    expires_at = timezone.now() + timedelta(
        seconds=TWO_FACTOR_CODE_LIFETIME_SECONDS
    )
    try:
        with transaction.atomic():
            TwoFactorEmailDelivery.objects.filter(
                user=user,
                status=TwoFactorEmailDelivery.QUEUED,
            ).delete()
            TwoFactorEmailDelivery.objects.create(
                user=user,
                nonce=nonce,
                expires_at=expires_at,
            )
    except Exception:
        logger.exception(
            "Two-factor verification email could not be queued for user_id=%s.",
            user.pk,
        )
        return False

    request.session[TWO_FACTOR_USER_SESSION_KEY] = user.pk
    request.session[TWO_FACTOR_HASH_SESSION_KEY] = make_password(code)
    request.session[TWO_FACTOR_EXPIRES_SESSION_KEY] = (
        now_timestamp + TWO_FACTOR_CODE_LIFETIME_SECONDS
    )
    request.session[TWO_FACTOR_ATTEMPTS_SESSION_KEY] = 0
    request.session[TWO_FACTOR_SENT_SESSION_KEY] = now_timestamp
    if backend:
        request.session[TWO_FACTOR_BACKEND_SESSION_KEY] = backend
    request.session.modified = True
    return True


@sensitive_post_parameters("password")
@never_cache
def login(request):
    if request.user.is_authenticated:
        return redirect(_portal_home_for_user(request.user))
    if request.method == 'POST':
        _clear_two_factor_session(request)
        identifier = (
            request.POST.get('identifier')
            or request.POST.get('email')
            or ''
        ).strip()
        password = request.POST.get('password', '')
        if identifier and password:
            matched_user = CustomUser.objects.filter(
                Q(email__iexact=identifier)
                | Q(username__iexact=identifier)
            ).only("username").first()
            authentication_username = (
                matched_user.username if matched_user else identifier
            )
            user = authenticate(
                username=authentication_username,
                password=password,
            )
            if user:
                if user.two_factor_enabled:
                    if not user.email:
                        messages.error(
                            request,
                            "Two-factor authentication is enabled, but this account has no email address. Contact an administrator.",
                        )
                        return redirect("login")
                    if _send_two_factor_code(
                        request,
                        user,
                        getattr(user, "backend", None),
                    ):
                        return redirect("two_factor_verify")
                    messages.error(
                        request,
                        "Your password was correct, but the verification email could not be queued. Try again.",
                    )
                    return redirect("login")
                auth_login(request, user)
                return redirect(_portal_home_for_user(user))
        messages.error(
            request,
            "The username, email address, or password is incorrect.",
        )
    return render(request, "login.html")


@sensitive_post_parameters("code")
@never_cache
def two_factor_verify(request):
    if request.user.is_authenticated:
        return redirect(_portal_home_for_user(request.user))
    user_id = request.session.get(TWO_FACTOR_USER_SESSION_KEY)
    code_hash = request.session.get(TWO_FACTOR_HASH_SESSION_KEY)
    expires_at = request.session.get(TWO_FACTOR_EXPIRES_SESSION_KEY)
    if not user_id or not code_hash or not expires_at:
        messages.error(request, "Start a new login to request a verification code.")
        return redirect("login")
    user = CustomUser.objects.filter(pk=user_id).first()
    if user is None:
        _clear_two_factor_session(request)
        messages.error(request, "This verification request is no longer valid.")
        return redirect("login")
    if not user.is_active or not user.approved or not user.two_factor_enabled:
        _clear_two_factor_session(request)
        messages.error(request, "This verification request is no longer valid.")
        return redirect("login")
    if int(timezone.now().timestamp()) > int(expires_at):
        _clear_two_factor_session(request)
        messages.error(request, "The verification code expired. Sign in again.")
        return redirect("login")

    if request.method == "POST":
        attempts = int(
            request.session.get(TWO_FACTOR_ATTEMPTS_SESSION_KEY, 0)
        ) + 1
        request.session[TWO_FACTOR_ATTEMPTS_SESSION_KEY] = attempts
        submitted_code = request.POST.get("code", "").strip().replace(" ", "")
        if (
            len(submitted_code) == 6
            and submitted_code.isdigit()
            and check_password(submitted_code, code_hash)
        ):
            backend = request.session.get(TWO_FACTOR_BACKEND_SESSION_KEY)
            _clear_two_factor_session(request)
            auth_login(request, user, backend=backend)
            messages.success(request, "Your sign-in was verified.")
            return redirect(_portal_home_for_user(user))
        if attempts >= TWO_FACTOR_MAX_ATTEMPTS:
            _clear_two_factor_session(request)
            messages.error(request, "Too many incorrect codes. Sign in again.")
            return redirect("login")
        remaining = TWO_FACTOR_MAX_ATTEMPTS - attempts
        messages.error(
            request,
            f"The verification code is incorrect. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
        )
    masked_email = (
        f"{user.email[:2]}***@{user.email.split('@', 1)[1]}"
        if "@" in user.email
        else "your account email"
    )
    return render(request, "portal/two_factor_verify.html", {
        "masked_email": masked_email,
        "resend_cooldown": TWO_FACTOR_RESEND_COOLDOWN_SECONDS,
    })


@require_POST
def two_factor_resend(request):
    if request.user.is_authenticated:
        return redirect(_portal_home_for_user(request.user))
    user_id = request.session.get(TWO_FACTOR_USER_SESSION_KEY)
    if not user_id:
        messages.error(request, "Start a new login to request a code.")
        return redirect("login")
    user = CustomUser.objects.filter(
        pk=user_id,
        is_active=True,
        approved=True,
        two_factor_enabled=True,
    ).first()
    if user is None:
        _clear_two_factor_session(request)
        messages.error(request, "This verification request is no longer valid.")
        return redirect("login")
    now_timestamp = int(timezone.now().timestamp())
    last_sent = int(request.session.get(TWO_FACTOR_SENT_SESSION_KEY, 0))
    if now_timestamp - last_sent < TWO_FACTOR_RESEND_COOLDOWN_SECONDS:
        messages.info(request, "Please wait before requesting another code.")
        return redirect("two_factor_verify")
    backend = request.session.get(TWO_FACTOR_BACKEND_SESSION_KEY)
    if _send_two_factor_code(request, user, backend):
        messages.success(request, "A new verification code was sent.")
    else:
        messages.error(request, "The verification email could not be sent.")
    return redirect("two_factor_verify")


@require_POST
@login_required
@approved_required
@sensitive_post_parameters("password")
def change_two_factor_setting(request):
    password = request.POST.get("password", "")
    enable = request.POST.get("enabled") == "true"
    if not request.user.check_password(password):
        messages.error(request, "Enter your current password to change two-factor authentication.")
        return redirect("profile")
    if enable and not request.user.email:
        messages.error(request, "Add an email address before enabling two-factor authentication.")
        return redirect("profile")
    request.user.two_factor_enabled = enable
    request.user.save(update_fields=["two_factor_enabled"])
    if enable:
        messages.success(request, "Email two-factor authentication is now enabled.")
    else:
        messages.success(request, "Email two-factor authentication is now disabled.")
    return redirect("profile")

@approved_required
@emailSender_required
@login_required
def calenderNotification(request: HttpRequest, year=None, month=None):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    local_today = timezone.localdate()
    if not year or not month:
        year = local_today.year
        month = local_today.month
    if not 1 <= month <= 12 or not 1900 <= year <= 2100:
        raise Http404("Invalid calendar month.")

    weekly_emails = WeeklyEmail.objects.filter(
        date_scheduled__year=year,
        date_scheduled__month=month,
    ).order_by("date_scheduled", "id")

    events_by_day = {}
    for event in weekly_emails:
        day = event.date_scheduled.day
        events_by_day.setdefault(day, []).append(event)

    cal = calendar.Calendar(firstweekday=0)
    weeks = [
        [
            {"day": day, "events": events_by_day.get(day, [])} if day else None
            for day in week
        ]
        for week in cal.monthdayscalendar(year, month)
    ]
    today = (
        local_today.day
        if year == local_today.year and month == local_today.month
        else None
    )

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
    context = {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "today": today,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "weeks": weeks,
        "events": weekly_emails,
        "profile_photo": profile_photo,
        "active_nav": "calendar",
    }
    return render(request, "portal/admin_calendar.html", context)

@require_POST
@login_required
@approved_required
@emailSender_required
def delete_email(request, email_id):
    email = get_object_or_404(WeeklyEmail, id=email_id)
    scheduled_date = email.date_scheduled
    email.delete()
    messages.success(request, "The scheduled event was deleted.")
    if scheduled_date:
        return redirect(
            "calenderNotification",
            scheduled_date.year,
            scheduled_date.month,
        )
    return redirect("calenderNotification")

@login_required
@approved_required
@emailSender_required
def calendarEventView(request: HttpRequest, email_id):
    profile_photo = request.user.profile_photos.order_by('-uploaded_at').first()
    email = get_object_or_404(WeeklyEmail, id=email_id)
    if not email.date_scheduled:
        messages.error(request, "This event does not have a scheduled date.")
        return redirect("calenderNotification")
    return render(request, "portal/admin_calendar_event.html", {
        "email": email,
        "day": email.date_scheduled.strftime("%A"),
        "profile_photo": profile_photo,
        "active_nav": "calendar",
    })
