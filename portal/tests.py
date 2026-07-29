from datetime import date
import re

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.db import IntegrityError, transaction

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
