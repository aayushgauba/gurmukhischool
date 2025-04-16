from django.shortcuts import render,HttpResponse, redirect
from .models import CarouselImage, BlacklistedIP
from pages.models import Contact
from portal.models import EmailSubscriber
from django.views.decorators.http import require_POST
from django.http import JsonResponse

def indexMain(request):
    images = CarouselImage.objects.all()
    images = images.order_by("order")
    return render(request,"main/index.html", {"images":images})

def aboutMain(request):
    return render(request,"main/about.html")

def sitemap(request):
    return HttpResponse(open('templates/sitemap.xml').read(), content_type='text/xml')

def subscribe(request):
    return render(request,"subscribe.html")

@require_POST
def subscribePOST(request):
    firstName = request.POST.get("firstName")
    lastName = request.POST.get("lastName")
    name = str(firstName + " " + lastName)
    email = request.POST.get("email")
    EmailSubscriber.objects.create(name = name, email = email)
    return redirect("indexMain")

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()
        honeypot = request.POST.get('website', '').strip()
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')
        if honeypot:
            BlacklistedIP.objects.get_or_create(
                ip_address=ip,
                defaults={'reason': 'Honeypot triggered'}
            )
            return JsonResponse({"status": "bot_detected"}, status=403)
        if name and email and message:
            Contact.objects.create(name=name, email=email, message=message, ip_address=ip)
            return redirect("indexMain")
        return JsonResponse({"status": "invalid_form"}, status=400)
    return render(request, 'contact.html')