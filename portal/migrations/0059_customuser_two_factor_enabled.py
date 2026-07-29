from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0058_customuser_contact_notifications_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="two_factor_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Require an emailed verification code after password login.",
            ),
        ),
    ]
