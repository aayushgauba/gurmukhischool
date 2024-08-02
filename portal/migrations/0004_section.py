# Generated by Django 5.0.6 on 2024-06-09 13:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0003_courses_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Title', models.CharField(max_length=20, unique=True)),
                ('Course_id', models.IntegerField()),
            ],
        ),
    ]