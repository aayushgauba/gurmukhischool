# Generated by Django 5.1.4 on 2025-04-14 20:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0002_contact_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
    ]
