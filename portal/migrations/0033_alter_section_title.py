# Generated by Django 5.0.6 on 2024-09-02 19:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0032_courses_syllabus'),
    ]

    operations = [
        migrations.AlterField(
            model_name='section',
            name='Title',
            field=models.CharField(max_length=200),
        ),
    ]
