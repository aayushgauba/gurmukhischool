# Generated by Django 5.0.6 on 2025-01-01 01:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0039_uploadedattendance'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadedattendance',
            name='student',
            field=models.CharField(max_length=10),
        ),
    ]
