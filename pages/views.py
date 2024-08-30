from django.shortcuts import render, redirect, HttpResponse
from .models import Contact
from portal.models import CarouselImage

def index(request):
    images = CarouselImage.objects.all()
    images = images.order_by("order")
    return render(request,"index.html", {"images":images})

def events(request):
    return render(request,"events.html")

def sitemap(request):
    return HttpResponse(open('templates/sitemap.xml').read(), content_type='text/xml')

def about(request):
    return render(request,"about.html")

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        if name and email and message:
            Contact.objects.create(name=name, email=email, message=message)
    return render(request, 'contact.html')