from django import forms
from .models import UploadedFile, filestoAssignment
from tinymce.widgets import TinyMCE
from .models import Announcement, Courses
from django_select2.forms import Select2MultipleWidget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

class UploadedFileForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ('file',)

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = filestoAssignment
        fields = ['file']

    def __init__(self, *args, **kwargs):
        user_id = kwargs.pop('user_id')
        assignment_id = kwargs.pop('assignment_id')
        super(FileUploadForm, self).__init__(*args, **kwargs)
        self.instance.user_id = user_id
        self.instance.assignment_id = assignment_id

class AnnouncementForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=Courses.objects.all(),
        widget=Select2MultipleWidget(attrs={'class': 'js-example-basic-multiple'}),
    )
    class Meta:
        model = Announcement
        fields = ['title', 'recipients', 'content']
