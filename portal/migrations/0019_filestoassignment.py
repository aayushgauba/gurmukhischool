# Generated by Django 5.0.6 on 2024-08-10 01:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0018_courses_people'),
    ]

    operations = [
        migrations.CreateModel(
            name='filestoAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(unique=True, upload_to='uploads/')),
                ('user_id', models.IntegerField()),
            ],
        ),
    ]