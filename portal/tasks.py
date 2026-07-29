import csv
import datetime
import io

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.tasks import task
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    Announcement,
    Attendance,
    CustomUser,
    EmailSubscriber,
    ProfilePhoto,
    UploadedAttendance,
    WeeklyEmail,
)


def _parse_attendance_date(value):
    for date_format in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized attendance date: {value!r}")


def _read_attendance_upload(field_file):
    field_file.open("rb")
    try:
        with io.TextIOWrapper(field_file.file, encoding="utf-8-sig") as stream:
            rows = csv.reader(stream)
            dates = next(rows)
            statuses = next(rows)
    finally:
        field_file.close()
    if len(dates) != len(statuses):
        raise ValueError("Attendance dates and statuses have different lengths.")
    status_map = {
        "P": "Present",
        "PRESENT": "Present",
        "A": "Absent",
        "ABSENT": "Absent",
    }
    parsed = []
    for date_value, status_value in zip(dates, statuses):
        normalized_status = status_map.get(status_value.strip().upper())
        if normalized_status is None:
            raise ValueError(f"Unrecognized attendance status: {status_value!r}")
        parsed.append((_parse_attendance_date(date_value), normalized_status))
    return parsed


@task
def process_attendance_uploads():
    processed = 0
    failed = 0
    for upload in UploadedAttendance.objects.select_related("student", "course"):
        try:
            attendance_rows = _read_attendance_upload(upload.file)
            with transaction.atomic():
                for attendance_date, status in attendance_rows:
                    Attendance.objects.update_or_create(
                        student=upload.student,
                        course=upload.course,
                        day=attendance_date.day,
                        month=attendance_date.month,
                        year=attendance_date.year,
                        defaults={"status": status},
                    )
                file_name = upload.file.name
                storage = upload.file.storage
                upload.delete()
            if file_name:
                storage.delete(file_name)
            processed += 1
        except Exception:
            failed += 1
    return {"processed": processed, "failed": failed}


@task
def transfer_legacy_profile_photos():
    linked = 0
    with transaction.atomic():
        for user in CustomUser.objects.exclude(profile_photo=""):
            if not user.profile_photo:
                continue
            photo, _ = ProfilePhoto.objects.get_or_create(
                file=user.profile_photo.name,
            )
            if not user.profile_photos.filter(pk=photo.pk).exists():
                user.profile_photos.add(photo)
                linked += 1
    return {"linked": linked}


@task
def normalize_user_permissions():
    updated = 0
    for user in CustomUser.objects.all().iterator():
        should_be_superuser = user.user_type in {
            CustomUser.TEACHER,
            CustomUser.ADMIN,
        }
        if user.is_superuser != should_be_superuser:
            user.is_superuser = should_be_superuser
            user.save(update_fields=["is_superuser"])
            updated += 1
    return {"updated": updated}


def _send_html_email(*, subject, body, html, recipients):
    recipients = sorted({email for email in recipients if email})
    if not recipients:
        return False
    message = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[],
        bcc=recipients,
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)
    return True


@task
def send_pending_emails():
    announcements_sent = 0
    announcements_failed = 0
    announcement_ids = list(
        Announcement.objects.filter(sent=False).values_list("id", flat=True)
    )
    for announcement_id in announcement_ids:
        try:
            with transaction.atomic():
                announcement = (
                    Announcement.objects.select_for_update()
                    .prefetch_related("recipients__people")
                    .get(pk=announcement_id)
                )
                if announcement.sent:
                    continue
                recipients = {
                    person.email
                    for course in announcement.recipients.all()
                    for person in course.people.all()
                    if person.email and person.is_active and person.approved
                }
                delivered = _send_html_email(
                    subject=f"New Announcement: {announcement.title}",
                    body=announcement.content,
                    html=render_to_string(
                        "email/announcementNotification.html",
                        {"announcement": announcement},
                    ),
                    recipients=recipients,
                )
                if delivered:
                    announcement.sent = True
                    announcement.save(update_fields=["sent"])
        except Exception:
            announcements_failed += 1
        else:
            if delivered:
                announcements_sent += 1
            else:
                announcements_failed += 1

    weekly_sent = 0
    weekly_failed = 0
    target_date = timezone.localdate() + datetime.timedelta(days=7)
    subscribers = list(
        EmailSubscriber.objects.exclude(email="").values_list("email", flat=True)
    )
    scheduled_email_ids = list(
        WeeklyEmail.objects.filter(
            sent=False,
            date_scheduled=target_date,
        ).values_list("id", flat=True)
    )
    for scheduled_email_id in scheduled_email_ids:
        try:
            with transaction.atomic():
                scheduled_email = WeeklyEmail.objects.select_for_update().get(
                    pk=scheduled_email_id,
                )
                if scheduled_email.sent:
                    continue
                delivered = _send_html_email(
                    subject=scheduled_email.subject or "Weekly Kirtan",
                    body=scheduled_email.organizer or "Weekly Kirtan",
                    html=render_to_string(
                        "email/weekly-kirtan-email.html",
                        {
                            "email": scheduled_email,
                            "day": scheduled_email.date_scheduled.strftime("%A"),
                        },
                    ),
                    recipients=subscribers,
                )
                if delivered:
                    scheduled_email.sent = True
                    scheduled_email.date_sent = timezone.localdate()
                    scheduled_email.save(update_fields=["sent", "date_sent"])
        except Exception:
            weekly_failed += 1
        else:
            if delivered:
                weekly_sent += 1
            else:
                weekly_failed += 1
    return {
        "announcements_sent": announcements_sent,
        "announcements_failed": announcements_failed,
        "weekly_sent": weekly_sent,
        "weekly_failed": weekly_failed,
    }


@task
def process_group_photos():
    from .models import GroupPhotoAttendance
    from photoattendance import scan_group_photos

    queued_before = GroupPhotoAttendance.objects.count()
    scan_group_photos()
    queued_after = GroupPhotoAttendance.objects.count()
    return {
        "processed": max(queued_before - queued_after, 0),
        "remaining": queued_after,
    }


@task
def spam_classifier_report():
    from pages.models import Contact
    from pages.spam_classifier import learn_spam_terms

    spam_messages = list(
        Contact.objects.filter(is_spam=True).values_list("message", flat=True)
    )
    legitimate_messages = list(
        Contact.objects.filter(is_spam=False).values_list("message", flat=True)
    )
    learned_terms = learn_spam_terms(spam_messages, legitimate_messages)
    return {
        "spam_messages": len(spam_messages),
        "legitimate_messages": len(legitimate_messages),
        "learned_terms": [
            {"term": term, "score": round(score, 3)}
            for term, score in sorted(
                learned_terms.items(),
                key=lambda item: (-item[1], item[0]),
            )[:50]
        ],
    }
