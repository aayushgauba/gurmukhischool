# Generated by Django 5.0.6 on 2024-12-31 18:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0035_announcement_sent'),
    ]

    operations = [
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('startDate', models.DateField()),
                ('endDate', models.DateField()),
                ('days', models.TextField()),
            ],
        ),
    ]