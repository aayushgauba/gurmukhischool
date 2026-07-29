import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0004_contact_is_spam"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MailboxMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("folder", models.CharField(default="INBOX", max_length=100)),
                ("uid", models.CharField(max_length=255)),
                ("message_id", models.CharField(blank=True, max_length=998)),
                ("sender_name", models.CharField(blank=True, max_length=255)),
                ("sender_email", models.EmailField(blank=True, max_length=254)),
                ("recipients", models.TextField(blank=True)),
                ("subject", models.CharField(blank=True, max_length=998)),
                ("body", models.TextField(blank=True)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("synced_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-received_at", "-id"]},
        ),
        migrations.CreateModel(
            name="MailDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("recipient", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=998)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("draft", "Draft"), ("queued", "Queued"), ("sent", "Sent")], default="draft", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("contact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="email_drafts", to="pages.contact")),
                ("created_by_name", models.CharField(blank=True, max_length=255)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mail_drafts", to=settings.AUTH_USER_MODEL)),
                ("reply_to_message", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replies", to="pages.mailboxmessage")),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="mailboxmessage",
            constraint=models.UniqueConstraint(fields=("folder", "uid"), name="unique_mailbox_folder_uid"),
        ),
    ]
