from django.db import migrations, models
import django.db.models.deletion


def remove_orphaned_relationships(apps, schema_editor):
    CustomUser = apps.get_model("portal", "CustomUser")
    Assignment = apps.get_model("portal", "Assignment")
    Courses = apps.get_model("portal", "Courses")
    Submission = apps.get_model("portal", "Submission")
    Folder = apps.get_model("portal", "Folder")
    Section = apps.get_model("portal", "Section")
    Grade = apps.get_model("portal", "Grade")

    valid_user_ids = CustomUser.objects.values("pk")
    valid_assignment_ids = Assignment.objects.values("pk")
    valid_course_ids = Courses.objects.values("pk")

    Submission.objects.exclude(user__in=valid_user_ids).delete()
    Submission.objects.exclude(assignment__in=valid_assignment_ids).delete()
    Folder.objects.exclude(course__in=valid_course_ids).delete()
    Section.objects.exclude(course__in=valid_course_ids).delete()
    Grade.objects.exclude(user__in=valid_user_ids).delete()
    Grade.objects.exclude(assignment__in=valid_assignment_ids).delete()
    Grade.objects.exclude(course__in=valid_course_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0055_normalize_legacy_field_names"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="filestoAssignment",
            new_name="Submission",
        ),
        migrations.RenameField(
            model_name="submission",
            old_name="user_id",
            new_name="user",
        ),
        migrations.RenameField(
            model_name="submission",
            old_name="assignment_id",
            new_name="assignment",
        ),
        migrations.RenameField(
            model_name="folder",
            old_name="course_id",
            new_name="course",
        ),
        migrations.RenameField(
            model_name="section",
            old_name="course_id",
            new_name="course",
        ),
        migrations.RenameField(
            model_name="grade",
            old_name="assignment_id",
            new_name="assignment",
        ),
        migrations.RenameField(
            model_name="grade",
            old_name="course_id",
            new_name="course",
        ),
        migrations.RenameField(
            model_name="grade",
            old_name="user_id",
            new_name="user",
        ),
        migrations.RunPython(
            remove_orphaned_relationships,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="submission",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="submissions",
                to="portal.customuser",
            ),
        ),
        migrations.AlterField(
            model_name="submission",
            name="assignment",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="submissions",
                to="portal.assignment",
            ),
        ),
        migrations.AlterField(
            model_name="folder",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="folders",
                to="portal.courses",
            ),
        ),
        migrations.AlterField(
            model_name="section",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sections",
                to="portal.courses",
            ),
        ),
        migrations.AlterField(
            model_name="grade",
            name="assignment",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="grades",
                to="portal.assignment",
            ),
        ),
        migrations.AlterField(
            model_name="grade",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="grades",
                to="portal.courses",
            ),
        ),
        migrations.AlterField(
            model_name="grade",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="grades",
                to="portal.customuser",
            ),
        ),
    ]
