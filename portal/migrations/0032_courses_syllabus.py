# Generated by Django 5.0.6 on 2024-08-25 20:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0031_alter_carouselimage_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='courses',
            name='Syllabus',
            field=models.FileField(blank=True, upload_to='syllabus/'),
        ),
    ]
