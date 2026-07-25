from django.db import migrations, models
import django.db.models.deletion


def deduplicate_grades(apps, schema_editor):
    Grade = apps.get_model("portal", "Grade")
    Grade.objects.filter(grade__lt=0).update(grade=0)
    Grade.objects.filter(grade__gt=100).update(grade=100)
    duplicates = (
        Grade.objects.values("assignment_id", "course_id", "user_id")
        .annotate(count=models.Count("id"), newest=models.Max("id"))
        .filter(count__gt=1)
    )
    for duplicate in duplicates.iterator():
        Grade.objects.filter(
            assignment_id=duplicate["assignment_id"],
            course_id=duplicate["course_id"],
            user_id=duplicate["user_id"],
        ).exclude(id=duplicate["newest"]).delete()
    CustomUser = apps.get_model("portal", "CustomUser")
    CustomUser.objects.filter(usertype="EmailSender").update(is_superuser=False)
    Schedule = apps.get_model("portal", "Schedule")
    duplicate_schedules = (
        Schedule.objects.values("course_id")
        .annotate(count=models.Count("id"), newest=models.Max("id"))
        .filter(count__gt=1)
    )
    for duplicate in duplicate_schedules.iterator():
        Schedule.objects.filter(course_id=duplicate["course_id"]).exclude(
            id=duplicate["newest"]
        ).delete()
    Courses = apps.get_model("portal", "Courses")
    Attendance = apps.get_model("portal", "Attendance")
    UploadedAttendance = apps.get_model("portal", "UploadedAttendance")
    student_course = {}
    student_ids = set(
        Attendance.objects.filter(course__isnull=True).values_list(
            "student_id", flat=True
        )
    )
    student_ids.update(
        UploadedAttendance.objects.filter(course__isnull=True).values_list(
            "student_id", flat=True
        )
    )
    for student_id in student_ids:
        course_ids = list(
            Courses.objects.filter(People__id=student_id).values_list(
                "id", flat=True
            )[:2]
        )
        if len(course_ids) == 1:
            student_course[student_id] = course_ids[0]
    for student_id, course_id in student_course.items():
        Attendance.objects.filter(
            student_id=student_id,
            course__isnull=True,
        ).update(course_id=course_id)
        UploadedAttendance.objects.filter(
            student_id=student_id,
            course__isnull=True,
        ).update(course_id=course_id)
    duplicate_attendance = (
        Attendance.objects.exclude(course__isnull=True)
        .values("student_id", "course_id", "day", "month", "year")
        .annotate(count=models.Count("id"), newest=models.Max("id"))
        .filter(count__gt=1)
    )
    for duplicate in duplicate_attendance.iterator():
        Attendance.objects.filter(
            student_id=duplicate["student_id"],
            course_id=duplicate["course_id"],
            day=duplicate["day"],
            month=duplicate["month"],
            year=duplicate["year"],
        ).exclude(id=duplicate["newest"]).delete()


class Migration(migrations.Migration):
    dependencies = [("portal", "0053_normalize_user_roles")]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attendance_records",
                to="portal.courses",
            ),
        ),
        migrations.AddField(
            model_name="uploadedattendance",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attendance_uploads",
                to="portal.courses",
            ),
        ),
        migrations.AddField(
            model_name="groupphotoattendance",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="group_photo_uploads",
                to="portal.courses",
            ),
        ),
        migrations.RunPython(deduplicate_grades, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="attendance",
            constraint=models.UniqueConstraint(
                fields=("student", "course", "day", "month", "year"),
                name="unique_student_course_attendance_day",
            ),
        ),
        migrations.AddConstraint(
            model_name="grade",
            constraint=models.UniqueConstraint(
                fields=("assignment_id", "course_id", "user_id"),
                name="unique_assignment_course_user_grade",
            ),
        ),
        migrations.AddConstraint(
            model_name="schedule",
            constraint=models.UniqueConstraint(
                fields=("course",),
                name="unique_schedule_per_course",
            ),
        ),
        migrations.AddConstraint(
            model_name="grade",
            constraint=models.CheckConstraint(
                check=models.Q(grade__gte=0, grade__lte=100),
                name="grade_between_0_and_100",
            ),
        ),
    ]
