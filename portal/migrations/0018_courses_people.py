# Generated by Django 5.0.6 on 2024-08-02 14:08

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0017_remove_assignment_folder_id_folder_assignments'),
    ]

    operations = [
        migrations.AddField(
            model_name='courses',
            name='People',
            field=models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL),
        ),
    ]
