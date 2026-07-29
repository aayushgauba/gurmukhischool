from django.shortcuts import render

from portal.models import CarouselImage


def index(request):
    images = CarouselImage.objects.order_by("order", "pk")
    return render(request, "index.html", {"images": images, "active_page": "home"})


def about(request):
    return render(request, "about.html", {"active_page": "about"})
