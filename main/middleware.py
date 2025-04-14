from django.http import JsonResponse
from .models import BlacklistedIP

class IPBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')
        if BlacklistedIP.objects.filter(ip_address=ip).exists():
            return JsonResponse({"status": "blocked", "message": "Your IP has been blocked."}, status=403)
        return self.get_response(request)
