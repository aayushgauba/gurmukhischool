from django import forms

from pages.models import Contact
from portal.models import EmailSubscriber
from portal.forms import validate_upload_size

from .models import CarouselImage

class CarouselImageForm(forms.ModelForm):
    image = forms.ImageField(validators=[validate_upload_size])
    class Meta:
        model = CarouselImage
        fields = ['title', 'image', 'description']


class ContactForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Contact
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Invalid submission.")
        return value


class NewsletterSubscriptionForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "given-name",
                "placeholder": "First Name",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "family-name",
                "placeholder": "Last Name",
            }
        ),
    )
    agree_terms = forms.BooleanField(
        label="I agree to receive emails from Sikh Study Circle of St. Louis.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = EmailSubscriber
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "email",
                    "placeholder": "Email Address",
                }
            ),
        }

    def save(self, commit=True):
        subscriber = super().save(commit=False)
        subscriber.name = (
            f"{self.cleaned_data['first_name']} {self.cleaned_data['last_name']}"
        ).strip()
        if commit:
            subscriber.save()
        return subscriber
