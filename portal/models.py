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

class filestoAssignment(models.Model):
    file = models.FileField(upload_to='uploads/', unique = True)
    user_id = models.IntegerField()
    assignment_id = models.IntegerField()
    Date = models.DateField(auto_now_add=True)

class Courses(models.Model):
    Title = models.CharField(max_length=20, unique=True)
    Description = models.TextField()
    Status = models.BooleanField(default=True)
    People = models.ManyToManyField(CustomUser, blank=True)

class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/', unique = True)

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    files = models.ManyToManyField(UploadedFile, blank=True)
    def __str__(self):
        return self.title

class Folder(models.Model):
    Title = models.CharField(max_length=200)
    Course_id = models.IntegerField()
    Files = models.ManyToManyField(UploadedFile, blank=True)
    Assignments = models.ManyToManyField(Assignment, blank=True)

class Section(models.Model):
    Title = models.CharField(max_length=200, unique=True)
    Course_id = models.IntegerField()
    ONum = models.IntegerField()
    Status = models.BooleanField(default=True)
    Folders = models.ManyToManyField(Folder, blank = True)