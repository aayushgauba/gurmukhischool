# Generated by Django 5.0.6 on 2024-07-29 15:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0016_alter_section_folders'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='assignment',
            name='folder_id',
        ),
        migrations.AddField(
            model_name='folder',
            name='Assignments',
            field=models.ManyToManyField(blank=True, to='portal.assignment'),
        ),
    ]
