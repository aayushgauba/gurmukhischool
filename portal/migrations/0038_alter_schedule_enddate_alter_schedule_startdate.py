# Generated by Django 5.0.6 on 2024-12-31 21:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0037_schedule_course'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schedule',
            name='endDate',
            field=models.CharField(max_length=7),
        ),
        migrations.AlterField(
            model_name='schedule',
            name='startDate',
            field=models.CharField(max_length=7),
        ),
    ]
