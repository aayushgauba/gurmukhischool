from datetime import date, timedelta
import re
from urllib.parse import urlparse

from django.core import mail
from django.contrib.auth.models import Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    Assignment,
    Course,
    CustomUser,
    Submission,
    Folder,
    Section,
    WeeklyEmail,
    Attendance,
    Grade,
)
from .forms import UploadedFileForm
from .decorators import admin_required, teacher_required, web_manager_required
from .views import _set_user_roles, registration, resend_activation
from pages.models import (
    ActivationEmailDelivery,
    AdminMessageNotification,
    Contact,
    MailboxMessage,
)
from pages.tasks import process_email_pipeline


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="configured@example.com",
    EMAIL_HOST_USER="configured@example.com",
    EMAIL_IMAP_HOST="",
)
class ManualMailboxNotificationTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="a-long-test-password",
            user_type=CustomUser.ADMIN,
            approved=True,
        )
        self.subscriber = CustomUser.objects.create_user(
            username="subscriber@example.com",
            email="subscriber@example.com",
            user_type=CustomUser.STUDENT,
            approved=True,
            contact_notifications_enabled=True,
        )
        self.client.force_login(self.admin)
        self.mailbox_message = MailboxMessage.objects.create(
            folder="INBOX",
            uid="manual-notify",
            sender_email="configured@example.com",
            subject="Message to share",
        )
        self.contact = Contact.objects.create(
            name="Website visitor",
            email="visitor@example.com",
            message="Please share this with the notification recipients.",
        )

    def test_notify_button_queues_mailbox_message(self):
        response = self.client.post(
            reverse("mailboxNotify", args=[self.mailbox_message.pk])
        )

        self.assertRedirects(response, reverse("adminContactView"))
        notification = AdminMessageNotification.objects.get(
            mailbox_message=self.mailbox_message
        )
        self.assertEqual(notification.status, AdminMessageNotification.QUEUED)

    def test_regular_email_pipeline_sends_manual_notification_to_recipients(self):
        self.client.post(reverse("mailboxNotify", args=[self.mailbox_message.pk]))

        result = process_email_pipeline.call()

        notification = AdminMessageNotification.objects.get(
            mailbox_message=self.mailbox_message
        )
        self.assertEqual(result["admin_notifications"]["sent"], 1)
        self.assertEqual(notification.status, AdminMessageNotification.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(
            mail.outbox[0].bcc,
            ["admin@example.com", "subscriber@example.com"],
        )

    def test_notify_again_requeues_sent_notification(self):
        notification = AdminMessageNotification.objects.create(
            mailbox_message=self.mailbox_message,
            status=AdminMessageNotification.SENT,
            sent_at=timezone.now(),
            last_error="old error",
        )

        self.client.post(reverse("mailboxNotify", args=[self.mailbox_message.pk]))

        notification.refresh_from_db()
        self.assertEqual(notification.status, AdminMessageNotification.QUEUED)
        self.assertIsNone(notification.sent_at)
        self.assertEqual(notification.last_error, "")

    def test_spam_message_cannot_be_queued_manually(self):
        self.mailbox_message.is_spam = True
        self.mailbox_message.save(update_fields=["is_spam"])

        response = self.client.post(
            reverse("mailboxNotify", args=[self.mailbox_message.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            AdminMessageNotification.objects.filter(
                mailbox_message=self.mailbox_message
            ).exists()
        )

    def test_notify_button_queues_contact_message(self):
        response = self.client.post(
            reverse("contactNotify", args=[self.contact.pk])
        )

        self.assertRedirects(response, reverse("adminContactView"))
        notification = AdminMessageNotification.objects.get(contact=self.contact)
        self.assertEqual(notification.status, AdminMessageNotification.QUEUED)

    def test_spam_contact_cannot_be_queued_manually(self):
        self.contact.is_spam = True
        self.contact.save(update_fields=["is_spam"])

        response = self.client.post(
            reverse("contactNotify", args=[self.contact.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            AdminMessageNotification.objects.filter(contact=self.contact).exists()
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="configured@example.com",
    EMAIL_IMAP_HOST="",
    ALLOWED_HOSTS=["testserver"],
)
class AccountActivationTests(TestCase):
    def test_registration_email_link_activates_new_account(self):
        request = RequestFactory().post(
            reverse("registration"),
            {
                "firstName": "New",
                "lastName": "Student",
                "username": "newstudent",
                "email": "newstudent@example.com",
                "phoneNumber": "(636) 555-0100",
                "password": "StrongPass!483",
                "confirmPassword": "StrongPass!483",
            },
        )
        request.session = {}
        request._messages = FallbackStorage(request)

        response = registration(request)

        self.assertEqual(response.status_code, 302)
        user = CustomUser.objects.get(username="newstudent")
        self.assertEqual(user.email, "newstudent@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 0)
        delivery = ActivationEmailDelivery.objects.get(user=user)
        self.assertEqual(delivery.status, ActivationEmailDelivery.QUEUED)

        task_result = process_email_pipeline.call()

        delivery.refresh_from_db()
        self.assertEqual(task_result["activations"]["sent"], 1)
        self.assertEqual(delivery.status, ActivationEmailDelivery.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["newstudent@example.com"])

        ActivationEmailDelivery.objects.filter(pk=delivery.pk).update(
            requested_at=timezone.now() - timedelta(minutes=6)
        )
        resend_request = RequestFactory().post(
            reverse("resend_activation"),
            {"email": "newstudent@example.com"},
        )
        resend_request.session = {}
        resend_request._messages = FallbackStorage(resend_request)

        resend_response = resend_activation(resend_request)

        self.assertEqual(resend_response.status_code, 302)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, ActivationEmailDelivery.QUEUED)
        self.assertEqual(len(mail.outbox), 1)

        resend_result = process_email_pipeline.call()

        self.assertEqual(resend_result["activations"]["sent"], 1)
        self.assertEqual(len(mail.outbox), 2)
        match = re.search(
            r'href="([^"]*/activate/[^"]+)"',
            mail.outbox[1].alternatives[0].content,
        )
        self.assertIsNotNone(match)
        activation_path = urlparse(match.group(1)).path
        resolved = resolve(activation_path)
        activation_request = RequestFactory().get(activation_path)

        activation_response = resolved.func(
            activation_request,
            **resolved.kwargs,
        )

        self.assertEqual(activation_response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)


class PortalSecurityTests(TestCase):
    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="a-long-test-password",
            user_type=CustomUser.STUDENT,
            approved=True,
        )
        self.other_student = CustomUser.objects.create_user(
            username="other@example.com",
            password="a-long-test-password",
            user_type=CustomUser.STUDENT,
            approved=True,
        )
        self.teacher = CustomUser.objects.create_superuser(
            username="teacher@example.com",
            password="a-long-test-password",
            user_type=CustomUser.TEACHER,
            approved=True,
        )
        self.sender = CustomUser.objects.create_user(
            username="sender@example.com",
            password="a-long-test-password",
            user_type=CustomUser.EMAIL_SENDER,
            approved=True,
        )
        self.course = Course.objects.create(title="Course", description="Test")
        self.course.people.add(self.student)
        self.section = Section.objects.create(
            title="Section", course_id=self.course.id, order=0
        )
        self.folder = Folder.objects.create(
            title="Folder", course_id=self.course.id
        )
        self.section.folders.add(self.folder)
        self.assignment = Assignment.objects.create(
            title="Assignment", description="Test", due_date=date.today()
        )
        self.folder.assignments.add(self.assignment)

    def test_anonymous_user_cannot_delete_calendar_event(self):
        event = WeeklyEmail.objects.create(email_type="weekly")
        response = self.client.post(reverse("delete_email", args=[event.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(WeeklyEmail.objects.filter(pk=event.pk).exists())

    def test_calendar_delete_rejects_get(self):
        event = WeeklyEmail.objects.create(email_type="weekly")
        self.client.force_login(self.sender)
        response = self.client.get(reverse("delete_email", args=[event.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(WeeklyEmail.objects.filter(pk=event.pk).exists())

    def test_student_cannot_access_another_course(self):
        self.client.force_login(self.other_student)
        response = self.client.get(reverse("course", args=[self.course.id]))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_foreign_folder_or_assignment(self):
        self.client.force_login(self.other_student)
        folder_response = self.client.get(
            reverse("folder", args=[self.section.id, self.folder.id])
        )
        assignment_response = self.client.get(
            reverse(
                "viewAssignment",
                args=[self.section.id, self.folder.id, self.assignment.id],
            )
        )
        self.assertEqual(folder_response.status_code, 403)
        self.assertEqual(assignment_response.status_code, 403)

    def test_student_cannot_delete_another_students_submission(self):
        submission = Submission.objects.create(
            file=SimpleUploadedFile("submission.txt", b"work"),
            user_id=self.student.id,
            assignment_id=self.assignment.id,
        )
        self.client.force_login(self.other_student)
        response = self.client.post(
            reverse(
                "deleteSubmission",
                args=[self.section.id, self.folder.id, self.assignment.id],
            ),
            {"submission_id": submission.id},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Submission.objects.filter(pk=submission.pk).exists())

    def test_reordering_rejects_get(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("moveSectionUp", args=[self.section.id]))
        self.assertEqual(response.status_code, 405)

    def test_submission_download_is_owner_only(self):
        submission = Submission.objects.create(
            file=SimpleUploadedFile("private.txt", b"private work"),
            user_id=self.student.id,
            assignment_id=self.assignment.id,
        )
        self.client.force_login(self.other_student)
        response = self.client.get(
            reverse("view_submission_file", args=[submission.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_password_reset_does_not_reveal_unknown_email(self):
        response = self.client.post(
            reverse("reset"), {"email": "missing@example.com"}
        )
        self.assertRedirects(response, reverse("login"))

    def test_attendance_is_scoped_to_course(self):
        other_course = Course.objects.create(
            title="Other Course",
            description="Test",
        )
        first = Attendance.objects.create(
            student=self.student,
            course=self.course,
            day=1,
            month=1,
            year=2026,
            status="Present",
        )
        second = Attendance.objects.create(
            student=self.student,
            course=other_course,
            day=1,
            month=1,
            year=2026,
            status="Absent",
        )
        self.assertNotEqual(first.course_id, second.course_id)

    def test_duplicate_grade_is_rejected(self):
        Grade.objects.create(
            user_id=self.student.id,
            course_id=self.course.id,
            assignment_id=self.assignment.id,
            grade=90,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Grade.objects.create(
                user_id=self.student.id,
                course_id=self.course.id,
                assignment_id=self.assignment.id,
                grade=80,
            )

    def test_dangerous_upload_extension_is_rejected(self):
        form = UploadedFileForm(
            files={"file": SimpleUploadedFile("payload.html", b"<script>")}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)

    def test_logout_rejects_get(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)

    def test_admin_cannot_delete_self(self):
        admin = CustomUser.objects.create_user(
            username="admin@example.com",
            password="a-long-test-password",
            user_type=CustomUser.ADMIN,
            approved=True,
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("delete_user"),
            {"user_id": admin.id},
        )
        self.assertRedirects(response, reverse("adminUsers"))
        self.assertTrue(CustomUser.objects.filter(id=admin.id).exists())


class MultipleRoleTests(TestCase):
    def setUp(self):
        self.teacher_group = Group.objects.get(name=CustomUser.TEACHER)
        self.web_manager_group = Group.objects.get(name=CustomUser.WEB_MANAGER)
        self.admin_group = Group.objects.get(name=CustomUser.ADMIN)
        self.user = CustomUser.objects.create_user(
            username="teacher-web@example.com",
            password="a-long-test-password",
            user_type=CustomUser.TEACHER,
            approved=True,
        )
        self.user.groups.add(self.teacher_group, self.web_manager_group)
        self.factory = RequestFactory()

    def _request_for(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_combined_roles_can_open_teacher_and_website_areas(self):
        view = lambda request: HttpResponse("ok")
        self.assertEqual(
            teacher_required(view)(self._request_for(self.user)).status_code,
            200,
        )
        self.assertEqual(
            web_manager_required(view)(self._request_for(self.user)).status_code,
            200,
        )

    def test_combined_roles_cannot_modify_roles(self):
        view = admin_required(lambda request: HttpResponse("ok"))
        with self.assertRaises(PermissionDenied):
            view(self._request_for(self.user))

    def test_admin_can_assign_multiple_roles(self):
        admin = CustomUser.objects.create_user(
            username="admin-roles@example.com",
            password="a-long-test-password",
            user_type=CustomUser.ADMIN,
            approved=True,
        )
        admin.groups.add(self.admin_group)
        self.assertEqual(
            admin_required(lambda request: HttpResponse("ok"))(
                self._request_for(admin)
            ).status_code,
            200,
        )
        _set_user_roles(
            self.user,
            {CustomUser.TEACHER, CustomUser.WEB_MANAGER},
        )
        self.user.save(update_fields=["user_type", "is_superuser", "is_staff"])
        self.assertSetEqual(
            set(self.user.groups.values_list("name", flat=True)),
            {CustomUser.TEACHER, CustomUser.WEB_MANAGER},
        )

    def test_student_cannot_be_combined_with_staff_role(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Student cannot be combined",
        ):
            _set_user_roles(
                self.user,
                {CustomUser.STUDENT, CustomUser.TEACHER},
            )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class TwoFactorAuthenticationTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="two-factor@example.com",
            email="two-factor@example.com",
            password="a-long-test-password",
            user_type=CustomUser.STUDENT,
            approved=True,
            is_active=True,
            two_factor_enabled=True,
        )

    def test_password_does_not_authenticate_until_code_is_verified(self):
        response = self.client.post(
            reverse("login"),
            {
                "email": self.user.username,
                "password": "a-long-test-password",
            },
        )
        self.assertRedirects(response, reverse("two_factor_verify"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r"\b(\d{6})\b", mail.outbox[0].body)
        self.assertIsNotNone(match)
        response = self.client.post(
            reverse("two_factor_verify"),
            {"code": match.group(1)},
        )
        self.assertRedirects(response, reverse("courses"))
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            self.user.pk,
        )

    def test_verified_code_cannot_be_reused(self):
        self.client.post(
            reverse("login"),
            {
                "email": self.user.username,
                "password": "a-long-test-password",
            },
        )
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.client.post(reverse("two_factor_verify"), {"code": code})
        self.client.logout()

        response = self.client.post(
            reverse("two_factor_verify"),
            {"code": code},
        )
        self.assertRedirects(response, reverse("login"))

    def test_incorrect_codes_are_bounded(self):
        self.client.post(
            reverse("login"),
            {
                "email": self.user.username,
                "password": "a-long-test-password",
            },
        )
        actual_code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        incorrect_code = "000000" if actual_code != "000000" else "111111"
        for _ in range(5):
            response = self.client.post(
                reverse("two_factor_verify"),
                {"code": incorrect_code},
            )
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("two_factor_user_id", self.client.session)
