from .models import CarouselImage
from django import forms

class CarouselImageForm(forms.ModelForm):
    class Meta:
        model = CarouselImage
        fields = ['title', 'image', 'description']