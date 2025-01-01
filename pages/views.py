from django.shortcuts import render, redirect
from .models import Contact
from portal.models import CarouselImage

def index(request):
    images = CarouselImage.objects.all()
    images = images.order_by("order")
    return render(request,"index.html", {"images":images})

def events(request):
    return render(request,"events.html")

def about(request):
    return render(request,"about.html")