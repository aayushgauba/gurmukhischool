from django.db import migrations, models


def normalize_roles(apps, schema_editor):
    CustomUser = apps.get_model("portal", "CustomUser")
    mapping = {
        "webmanager": "WebManager",
        "admin": "Admin",
        "teacher": "Teacher",
        "student": "Student",
        "parent": "Parent",
        "emailsender": "EmailSender",
    }
    for old_value, new_value in mapping.items():
        CustomUser.objects.filter(usertype__iexact=old_value).update(usertype=new_value)


class Migration(migrations.Migration):
    dependencies = [("portal", "0052_emailsubscriber")]

    operations = [
        migrations.RunPython(normalize_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customuser",
            name="usertype",
            field=models.CharField(
                blank=True,
                choices=[
                    ("WebManager", "Web Manager"),
                    ("Admin", "Admin"),
                    ("Teacher", "Teacher"),
                    ("Student", "Student"),
                    ("Parent", "Parent"),
                    ("EmailSender", "Email Sender"),
                ],
                max_length=20,
            ),
        ),
    ]
