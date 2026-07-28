from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0054_attendance_course_and_grade_integrity"),
    ]

    operations = [
        migrations.RenameField("courses", "Title", "title"),
        migrations.RenameField("courses", "Description", "description"),
        migrations.RenameField("courses", "Status", "status"),
        migrations.RenameField("courses", "Syllabus", "syllabus"),
        migrations.RenameField("courses", "People", "people"),
        migrations.RenameField("folder", "Title", "title"),
        migrations.RenameField("folder", "Course_id", "course_id"),
        migrations.RenameField("folder", "Files", "files"),
        migrations.RenameField("folder", "Assignments", "assignments"),
        migrations.RenameField("section", "Title", "title"),
        migrations.RenameField("section", "Course_id", "course_id"),
        migrations.RenameField("section", "ONum", "order"),
        migrations.RenameField("section", "Status", "status"),
        migrations.RenameField("section", "Folders", "folders"),
        migrations.RenameField("filestoassignment", "Date", "date"),
    ]
