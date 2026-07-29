from django.db import migrations, models


def mark_existing_spam_as_reviewed(apps, schema_editor):
    Contact = apps.get_model("pages", "Contact")
    Contact.objects.filter(is_spam=True).update(spam_reviewed=True)


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0005_mailboxmessage_maildraft"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="spam_reviewed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mailboxmessage",
            name="is_spam",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mailboxmessage",
            name="spam_reviewed",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            mark_existing_spam_as_reviewed,
            migrations.RunPython.noop,
        ),
    ]
