# Generated by Django 5.0.6 on 2024-08-10 03:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0019_filestoassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='filestoassignment',
            name='assignment_id',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]