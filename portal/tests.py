from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import (
    Assignment,
    Courses,
    CustomUser,
    filestoAssignment,
    Folder,
    Section,
    WeeklyEmail,
)


class PortalSecurityTests(TestCase):
    def setUp(self):
        self.student = CustomUser.objects.create_user(
            username="student@example.com",
            password="a-long-test-password",
            usertype=CustomUser.STUDENT,
            approved=True,
        )
        self.other_student = CustomUser.objects.create_user(
            username="other@example.com",
            password="a-long-test-password",
            usertype=CustomUser.STUDENT,
            approved=True,
        )
        self.teacher = CustomUser.objects.create_superuser(
            username="teacher@example.com",
            password="a-long-test-password",
            usertype=CustomUser.TEACHER,
            approved=True,
        )
        self.sender = CustomUser.objects.create_user(
            username="sender@example.com",
            password="a-long-test-password",
            usertype=CustomUser.EMAIL_SENDER,
            approved=True,
        )
        self.course = Courses.objects.create(Title="Course", Description="Test")
        self.course.People.add(self.student)
        self.section = Section.objects.create(
            Title="Section", Course_id=self.course.id, ONum=0
        )
        self.folder = Folder.objects.create(
            Title="Folder", Course_id=self.course.id
        )
        self.section.Folders.add(self.folder)
        self.assignment = Assignment.objects.create(
            title="Assignment", description="Test", due_date=date.today()
        )
        self.folder.Assignments.add(self.assignment)

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
        submission = filestoAssignment.objects.create(
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
        self.assertTrue(filestoAssignment.objects.filter(pk=submission.pk).exists())

    def test_reordering_rejects_get(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("moveSectionUp", args=[self.section.id]))
        self.assertEqual(response.status_code, 405)

    def test_submission_download_is_owner_only(self):
        submission = filestoAssignment.objects.create(
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
