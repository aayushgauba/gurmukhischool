from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models

class ProfilePhoto(models.Model):
    file = models.FileField(upload_to="profile_photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo uploaded on {self.uploaded_at}"

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

    profile_photo = models.FileField(upload_to='profile_photos/', blank=True, null=True)
    profile_photos = models.ManyToManyField(
        ProfilePhoto,
        related_name='users',
        blank=True
    )
    usertype = models.CharField(max_length=20, choices=USER_TYPES, blank = True)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique = False)
    birth_date = models.DateField(blank=True, null=True)
    approved = models.BooleanField(blank=False, default=False)
    def __str__(self):
        return self.first_name +" "+ self.last_name

class CarouselImage(models.Model):
    title = models.CharField(max_length=100)
    image = models.FileField(upload_to='carousel_images/')
    order = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField()
    def __str__(self):
        return self.title

class filestoAssignment(models.Model):
    file = models.FileField(upload_to='uploads/', unique = True)
    user_id = models.IntegerField()
    assignment_id = models.IntegerField()
    Date = models.DateField(auto_now_add=True)

class Courses(models.Model):
    Title = models.CharField(max_length=20, unique=True)
    Description = models.TextField()
    Status = models.BooleanField(default=True)
    Syllabus = models.FileField(upload_to='syllabus/', blank=True)
    People = models.ManyToManyField(CustomUser, blank=True)
    def __str__(self):
        return self.Title
    
class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/', unique = True)

class UploadedAttendance(models.Model):
    file = models.FileField(upload_to='attendance/')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    files = models.ManyToManyField(UploadedFile, blank=True)
    def __str__(self):
        return self.title

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    recipients = models.ManyToManyField(Courses, blank=False)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)

class Attendance(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    day = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()  # Optional if you need to track the year
    status = models.CharField(max_length=10, choices=[('Present', 'Present'), ('Absent', 'Absent')])

class Folder(models.Model):
    Title = models.CharField(max_length=200)
    Course_id = models.IntegerField()
    Files = models.ManyToManyField(UploadedFile, blank=True)
    Assignments = models.ManyToManyField(Assignment, blank=True)

class Section(models.Model):
    Title = models.CharField(max_length=200)
    Course_id = models.IntegerField()
    ONum = models.IntegerField()
    Status = models.BooleanField(default=True)
    Folders = models.ManyToManyField(Folder, blank = True)

class Grade(models.Model):
    assignment_id = models.IntegerField()
    course_id = models.IntegerField()
    user_id = models.IntegerField()
    grade = models.FloatField()

class Schedule(models.Model):
    startDate = models.CharField(max_length=7)
    endDate = models.CharField(max_length=7)
    days = models.TextField()
    course = models.ForeignKey(Courses, on_delete=models.CASCADE)

class GroupPhotoAttendance(models.Model):
    file = models.FileField(upload_to='group_photo/', unique = True)