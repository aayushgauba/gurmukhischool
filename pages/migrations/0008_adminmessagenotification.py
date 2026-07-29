from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0007_twofactoremaildelivery"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminMessageNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("sent", "Sent"),
                            ("skipped", "Skipped"),
                        ],
                        default="queued",
                        max_length=10,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "contact",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admin_notification",
                        to="pages.contact",
                    ),
                ),
                (
                    "mailbox_message",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admin_notification",
                        to="pages.mailboxmessage",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
