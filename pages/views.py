from django.shortcuts import render

def index(request):
    return render(request,"index.html")

def login(request):
    return render(request,"login.html")

def events(request):
    return render(request,"events.html")

def registration(request):
    return render(request,"registration.html")

def about(request):
    return render(request,"about.html")

def contact(request):
    return render(request,"contact.html")
