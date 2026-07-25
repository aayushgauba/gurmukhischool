from .models import CarouselImage
from django import forms
from portal.forms import validate_upload_size

class CarouselImageForm(forms.ModelForm):
    image = forms.ImageField(validators=[validate_upload_size])
    class Meta:
        model = CarouselImage
        fields = ['title', 'image', 'description']
