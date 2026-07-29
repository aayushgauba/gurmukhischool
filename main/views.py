from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import get_template
from django.views.decorators.http import require_POST

from .forms import ContactForm, NewsletterSubscriptionForm
from .models import CarouselImage

def indexMain(request):
    images = CarouselImage.objects.order_by("order", "pk")
    return render(request, "main/index.html", {"images": images, "active_page": "home"})

def aboutMain(request):
    return render(request, "main/about.html", {"active_page": "about"})

def sitemap(request):
    content = get_template("sitemap.xml").render({"request": request})
    return HttpResponse(content, content_type="application/xml")

def subscribe(request):
    return render(
        request,
        "subscribe.html",
        {"form": NewsletterSubscriptionForm(), "active_page": "subscribe"},
    )

@require_POST
def subscribePOST(request):
    form = NewsletterSubscriptionForm(request.POST)
    if form.is_valid():
        form.save()
        return redirect("indexMain")
    return render(
        request,
        "subscribe.html",
        {"form": form, "active_page": "subscribe"},
        status=400,
    )

def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            contact_message = form.save(commit=False)
            contact_message.ip_address = request.META.get("REMOTE_ADDR")
            contact_message.save()
            return redirect("indexMain")
    return render(
        request,
        "contact.html",
        {"form": form, "active_page": "contact"},
        status=400 if request.method == "POST" else 200,
    )
