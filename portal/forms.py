from django import forms
from .models import UploadedFile, filestoAssignment

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
