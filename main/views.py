from django.shortcuts import render,HttpResponse
from .models import CarouselImage
from pages.models import Contact

def indexMain(request):
    images = CarouselImage.objects.all()
    images = images.order_by("order")
    return render(request,"main/index.html", {"images":images})

def aboutMain(request):
    return render(request,"main/about.html")

def sitemap(request):
    return HttpResponse(open('templates/sitemap.xml').read(), content_type='text/xml')

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        if name and email and message:
            Contact.objects.create(name=name, email=email, message=message)
    return render(request, 'contact.html')