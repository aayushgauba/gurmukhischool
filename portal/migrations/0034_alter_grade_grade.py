# Generated by Django 5.0.6 on 2024-12-23 00:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0033_alter_section_title'),
    ]

    operations = [
        migrations.AlterField(
            model_name='grade',
            name='grade',
            field=models.FloatField(),
        ),
    ]
