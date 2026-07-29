from django import forms

from .models import MailDraft


class MailComposeForm(forms.ModelForm):
    class Meta:
        model = MailDraft
        fields = ["recipient", "subject", "body"]
        widgets = {
            "recipient": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "email"}
            ),
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 12}),
        }
