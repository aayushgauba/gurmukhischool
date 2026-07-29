from django import forms
from .models import UploadedFile,UploadedAttendance, Submission
from .models import Announcement, Course, CustomUser, CarouselImage, GroupPhotoAttendance, ProfilePhoto
from django_select2.forms import Select2MultipleWidget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db.models import Q

MAX_UPLOAD_SIZE = 20 * 1024 * 1024
DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg']


def validate_upload_size(upload):
    if upload.size > MAX_UPLOAD_SIZE:
        raise ValidationError("files must be 20 MB or smaller.")


def validated_file_field(extensions):
    return forms.FileField(validators=[
        FileExtensionValidator(allowed_extensions=extensions),
        validate_upload_size,
    ])

class UploadedFileForm(forms.ModelForm):
    file = validated_file_field(DOCUMENT_EXTENSIONS)
    class Meta:
        model = UploadedFile
        fields = ['file']

class UploadedAttendanceForm(forms.ModelForm):
    file = validated_file_field(['csv'])
    student = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
    )
    class Meta:
        model = UploadedAttendance
        fields = ['file','student']

    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        students = CustomUser.objects.filter(
            Q(user_type=CustomUser.STUDENT)
            | Q(groups__name=CustomUser.STUDENT)
        ).distinct()
        if course is not None:
            students = students.filter(
                id__in=course.people.values_list('id', flat=True)
            )
        self.fields['student'].queryset = students
    

class CarouselImageForm(forms.ModelForm):
    image = forms.ImageField(validators=[validate_upload_size])
    class Meta:
        model = CarouselImage
        fields = ['title', 'image', 'description']

class SyllabusUploadForm(forms.ModelForm):
    syllabus = validated_file_field(['pdf'])
    class Meta:
        model = Course
        fields = ['syllabus']  # Only include the syllabus field

class ProfilePhotoForm(forms.ModelForm):
    file = forms.ImageField(validators=[validate_upload_size])
    class Meta:
        model = ProfilePhoto
        fields = ['file']

class FileUploadForm(forms.ModelForm):
    file = validated_file_field(DOCUMENT_EXTENSIONS)
    class Meta:
        model = Submission
        fields = ['file']

    def __init__(self, *args, **kwargs):
        user_id = kwargs.pop('user_id')
        assignment_id = kwargs.pop('assignment_id')
        super(FileUploadForm, self).__init__(*args, **kwargs)
        self.instance.user_id = user_id
        self.instance.assignment_id = assignment_id

class GroupPhotoUploadForm(forms.ModelForm):
    file = forms.ImageField(validators=[validate_upload_size])
    class Meta:
        model = GroupPhotoAttendance
        fields = ['file']

class AnnouncementForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all(),
        widget=Select2MultipleWidget(attrs={'class': 'js-example-basic-multiple'}),
    )
    class Meta:
        model = Announcement
        fields = ['title', 'recipients', 'content']
