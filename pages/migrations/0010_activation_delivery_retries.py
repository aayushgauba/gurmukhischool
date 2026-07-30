from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0009_activationemaildelivery"),
    ]

    operations = [
        migrations.AddField(
            model_name="activationemaildelivery",
            name="requested_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="activationemaildelivery",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("sent", "Sent"),
                    ("failed", "Failed"),
                ],
                default="queued",
                max_length=10,
            ),
        ),
    ]
