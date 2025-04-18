# Generated by Django 5.1.4 on 2025-02-02 00:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0046_profilephoto_customuser_profile_photos'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='embedding',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='modified_profile_photo',
            field=models.BooleanField(default=True),
        ),
    ]
