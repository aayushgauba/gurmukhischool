from django import forms
from .models import UploadedFile

class UploadedFileForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ('file', 'folder_id')
        widgets = {
            'folder_id': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        folder_id = kwargs.pop('folder_id', None)
        super(UploadedFileForm, self).__init__(*args, **kwargs)
        if folder_id is not None:
            self.fields['folder_id'].initial = folder_id
