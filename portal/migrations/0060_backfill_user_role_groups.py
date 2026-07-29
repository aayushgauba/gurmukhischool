from django.db import migrations


ROLE_NAMES = (
    "WebManager",
    "Admin",
    "Teacher",
    "Student",
    "Parent",
    "EmailSender",
)


def backfill_role_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    CustomUser = apps.get_model("portal", "CustomUser")

    groups = {
        role: Group.objects.get_or_create(name=role)[0]
        for role in ROLE_NAMES
    }
    for user in CustomUser.objects.exclude(user_type="").iterator():
        group = groups.get(user.user_type)
        if group is not None:
            user.groups.add(group)
    CustomUser.objects.filter(user_type="Teacher").update(
        is_superuser=False,
        is_staff=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0059_customuser_two_factor_enabled"),
    ]

    operations = [
        migrations.RunPython(backfill_role_groups, migrations.RunPython.noop),
    ]
