from django.http import JsonResponse
from .models import BlacklistedIP
import time
from collections import defaultdict
from main.models import BlacklistedIP

request_log = defaultdict(list)

def get_ip(request):
    return request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')

class AdaptiveRateLimiterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_ip(request)
        if BlacklistedIP.objects.filter(ip_address=ip).exists():
            return JsonResponse({"status": "blocked", "message": "Your IP has been blocked."}, status=403)
        now = time.time()
        window = 10
        request_log[ip] = [ts for ts in request_log[ip] if now - ts < window]
        request_log[ip].append(now)
        if len(request_log[ip]) > 20:
            return JsonResponse({"status": "too_many_requests", "message": "Slow down."}, status=429)
        if len(request_log[ip]) > 10:
            from .ai_throttle import evaluate_ip
            if evaluate_ip(ip, request_log[ip]):
                BlacklistedIP.objects.get_or_create(ip_address=ip, reason="AI-detected flood pattern")
                return JsonResponse({"status": "blocked", "message": "Suspicious activity detected."}, status=403)

        return self.get_response(request)

class IPBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')
        if BlacklistedIP.objects.filter(ip_address=ip).exists():
            return JsonResponse({"status": "blocked", "message": "Your IP has been blocked."}, status=403)
        return self.get_response(request)


