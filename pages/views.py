from django.shortcuts import render, redirect
from .models import Contact


def index(request):
    return render(request,"index.html")



def events(request):
    return render(request,"events.html")



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