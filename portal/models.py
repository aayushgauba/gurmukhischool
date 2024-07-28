from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    WEB_MANAGER = 'webmanager'
    ADMIN = 'admin'
    TEACHER = 'teacher'
    STUDENT = 'student'
    PARENT = 'parent'

    USER_TYPES = [
        (WEB_MANAGER, 'Web Manager'),
        (ADMIN, 'Admin'),
        (TEACHER, 'Teacher'),
        (STUDENT, 'Student'),
        (PARENT, 'Parent'),
    ]

    # Add usertype field
    usertype = models.CharField(max_length=20, choices=USER_TYPES, blank = True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    
class Courses(models.Model):
    Title = models.CharField(max_length=20, unique=True)
    Description = models.TextField()
    Status = models.BooleanField(default=True)

class Section(models.Model):
    Title = models.CharField(max_length=200, unique=True)
    Course_id = models.IntegerField()
    ONum = models.IntegerField()
    Status = models.BooleanField(default=True)

class UploadedFile(models.Model):
    folder_id = models.IntegerField(blank = True, null=True)
    file = models.FileField(upload_to='uploads/', unique = True)

class Folder(models.Model):
    Title = models.CharField(max_length=200)
    Course_id = models.IntegerField()
    Section_id = models.IntegerField()

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    folder_id = models.IntegerField()
    files = models.ManyToManyField(UploadedFile, blank=True)
    def __str__(self):
        return self.title

