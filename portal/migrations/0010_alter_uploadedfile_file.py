# Generated by Django 5.0.6 on 2024-06-21 04:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0009_uploadedfile_folder_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadedfile',
            name='file',
            field=models.FileField(unique=True, upload_to='uploads/'),
        ),
    ]
