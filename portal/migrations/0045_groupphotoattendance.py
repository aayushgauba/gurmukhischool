# Generated by Django 5.0.6 on 2025-01-02 03:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0044_alter_uploadedattendance_student'),
    ]

    operations = [
        migrations.CreateModel(
            name='GroupPhotoAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(unique=True, upload_to='group_photo/')),
            ],
        ),
    ]
