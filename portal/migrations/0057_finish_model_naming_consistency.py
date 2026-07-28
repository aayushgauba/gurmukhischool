from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0056_relational_integrity"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Courses",
            new_name="Course",
        ),
        migrations.RenameField(
            model_name="customuser",
            old_name="usertype",
            new_name="user_type",
        ),
        migrations.RenameField(
            model_name="schedule",
            old_name="startDate",
            new_name="start_date",
        ),
        migrations.RenameField(
            model_name="schedule",
            old_name="endDate",
            new_name="end_date",
        ),
    ]
