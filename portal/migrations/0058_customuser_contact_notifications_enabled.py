from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0057_finish_model_naming_consistency"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="contact_notifications_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Send this user an email when a public contact message arrives.",
            ),
        ),
    ]
