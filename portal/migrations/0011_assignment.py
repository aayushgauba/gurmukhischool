# Generated by Django 5.0.6 on 2024-07-27 14:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0010_alter_uploadedfile_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('due_date', models.DateField()),
                ('files', models.ManyToManyField(blank=True, to='portal.uploadedfile')),
            ],
        ),
    ]
