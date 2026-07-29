from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.functional import cached_property

class ProfilePhoto(models.Model):
    file = models.FileField(upload_to="profile_photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo uploaded on {self.uploaded_at}"

class CustomUser(AbstractUser):
    WEB_MANAGER = 'WebManager'
    ADMIN = 'Admin'
    TEACHER = 'Teacher'
    STUDENT = 'Student'
    PARENT = 'Parent'
    EMAIL_SENDER = 'EmailSender'

    USER_TYPES = [
        (WEB_MANAGER, 'Web Manager'),
        (ADMIN, 'Admin'),
        (TEACHER, 'Teacher'),
        (STUDENT, 'Student'),
        (PARENT, 'Parent'),
        (EMAIL_SENDER, 'Email Sender'),
    ]
    ROLE_VALUES = frozenset(
        (WEB_MANAGER, ADMIN, TEACHER, STUDENT, PARENT, EMAIL_SENDER)
    )
    STAFF_ROLES = frozenset((WEB_MANAGER, ADMIN, TEACHER, EMAIL_SENDER))

    profile_photo = models.FileField(upload_to='profile_photos/', blank=True, null=True)
    profile_photos = models.ManyToManyField(
        ProfilePhoto,
        related_name='users',
        blank=True
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPES, blank = True)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique = False)
    birth_date = models.DateField(blank=True, null=True)
    approved = models.BooleanField(blank=False, default=False)
    contact_notifications_enabled = models.BooleanField(
        default=False,
        help_text="Send this user an email when a public contact message arrives.",
    )
    two_factor_enabled = models.BooleanField(
        default=False,
        help_text="Require an emailed verification code after password login.",
    )
    embedding = models.JSONField(blank=True, null=True)
    modified_profile_photo = models.BooleanField(default=True)

    @classmethod
    def role_validation_error(cls, roles):
        roles = set(roles)
        if cls.STUDENT in roles and roles.intersection(cls.STAFF_ROLES):
            return (
                "Student cannot be combined with Teacher, Admin, "
                "Web Manager, or Email Sender."
            )
        return None

    @cached_property
    def role_names(self):
        roles = set(
            self.groups.filter(name__in=self.ROLE_VALUES).values_list("name", flat=True)
        )
        # Keep legacy accounts functional until every deployment has run the
        # group backfill migration.
        if self.user_type in self.ROLE_VALUES:
            roles.add(self.user_type)
        return roles

    def has_role(self, *roles):
        return bool(self.role_names.intersection(roles))

    @property
    def is_admin(self):
        return self.has_role(self.ADMIN)

    @property
    def is_teacher(self):
        return self.has_role(self.TEACHER)

    @property
    def is_student(self):
        return self.has_role(self.STUDENT)

    @property
    def is_web_manager(self):
        return self.has_role(self.WEB_MANAGER)

    @property
    def is_email_sender(self):
        return self.has_role(self.EMAIL_SENDER)

    @property
    def role_display(self):
        labels = dict(self.USER_TYPES)
        ordered_roles = [
            labels[value] for value, _label in self.USER_TYPES if value in self.role_names
        ]
        return ", ".join(ordered_roles) or "No role assigned"

    def __str__(self):
        return self.get_full_name() or self.username

class CarouselImage(models.Model):
    title = models.CharField(max_length=100)
    image = models.FileField(upload_to='carousel_images/')
    order = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField()
    def __str__(self):
        return self.title

class Submission(models.Model):
    file = models.FileField(upload_to='uploads/', unique = True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    assignment = models.ForeignKey(
        'Assignment',
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    date = models.DateField(auto_now_add=True)

class Course(models.Model):
    title = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    status = models.BooleanField(default=True)
    syllabus = models.FileField(upload_to='syllabus/', blank=True)
    people = models.ManyToManyField(CustomUser, blank=True)
    def __str__(self):
        return self.title
    
class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/', unique = True)

class UploadedAttendance(models.Model):
    file = models.FileField(upload_to='attendance/')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='attendance_uploads',
        null=True,
        blank=True,
    )

class EmailSubscriber(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    def __str__(self):
        return self.name

class WeeklyEmail(models.Model):
    email_type = models.CharField(max_length=50)
    organizer = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Organizer information (max 500 characters)"
    )
    date_created = models.DateField(auto_now_add=True)
    date_scheduled = models.DateField(null=True, blank=True)
    date_sent = models.DateField(null=True, blank=True)
    sent = models.BooleanField(default=False)
    subject = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return f"{self.email_type.capitalize()} Weekly Email (ID: {self.pk})"

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    files = models.ManyToManyField(UploadedFile, blank=True)
    def __str__(self):
        return self.title

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    recipients = models.ManyToManyField(Course, blank=False)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)

class Attendance(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        null=True,
        blank=True,
    )
    day = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()  # Optional if you need to track the year
    status = models.CharField(max_length=10, choices=[('Present', 'Present'), ('Absent', 'Absent')])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course', 'day', 'month', 'year'],
                name='unique_student_course_attendance_day',
            ),
        ]

class Folder(models.Model):
    title = models.CharField(max_length=200)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='folders',
    )
    files = models.ManyToManyField(UploadedFile, blank=True)
    assignments = models.ManyToManyField(Assignment, blank=True)

class Section(models.Model):
    title = models.CharField(max_length=200)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    order = models.IntegerField()
    status = models.BooleanField(default=True)
    folders = models.ManyToManyField(Folder, blank = True)

class Grade(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='grades',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='grades',
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='grades',
    )
    grade = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'course', 'user'],
                name='unique_assignment_course_user_grade',
            ),
        ]

class Schedule(models.Model):
    start_date = models.CharField(max_length=7)
    end_date = models.CharField(max_length=7)
    days = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['course'],
                name='unique_schedule_per_course',
            ),
        ]

class GroupPhotoAttendance(models.Model):
    file = models.FileField(upload_to='group_photo/', unique = True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='group_photo_uploads',
        null=True,
        blank=True,
    )
