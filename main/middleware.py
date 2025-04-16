from django.http import JsonResponse
from .models import BlacklistedIP
import time
from collections import defaultdict
import joblib
from main.models import BlacklistedIP
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
MODEL_PATH = "ai_ip_bot_detector_model.pkl"
import numpy as np
model = joblib.load(MODEL_PATH)
malicious_keywords = [".php", "xmlrpc", "wp-", ".env", ".git", ".bak", "conflg", "shell", "filemanager"]
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
    
class AIAnomalyMiddleware(MiddlewareMixin):
    WINDOW_SECONDS = 60
    def process_request(self, request):
        ip = self.get_ip(request)
        if BlacklistedIP.objects.filter(ip_address=ip).exists():
            return JsonResponse({"status": "blocked", "message": "IP is already in blocklist."}, status=403)
        now = time.time()
        key = f"ai_data:{ip}"
        request_data = cache.get(key, [])
        path = request.path
        path_len = len(path)
        kw_hits = sum(1 for kw in malicious_keywords if kw in path.lower())
        status_code = 404 if "not-found" in path.lower() else 200
        status_idx = ["200", "403", "404", "500"].index(str(status_code)) if str(status_code) in ["200", "403", "404", "500"] else -1
        response_time = 0.01  # Replace with real value if available
        request_data.append((now, path_len, kw_hits, status_idx, response_time))
        request_data = [entry for entry in request_data if now - entry[0] < self.WINDOW_SECONDS]
        cache.set(key, request_data, timeout=self.WINDOW_SECONDS)
        if len(request_data) < 5:
            return None
        burst_count = sum(1 for entry in request_data if now - entry[0] <= 10)
        total_404 = sum(1 for entry in request_data if entry[3] == 2)
        avg_resp_time = np.mean([entry[4] for entry in request_data])
        latest = request_data[-1]
        X = np.array([[latest[1], latest[2], avg_resp_time, latest[3], burst_count, total_404]], dtype=float)
        pred = model.predict(X)[0]
        if pred == -1:
            BlacklistedIP.objects.get_or_create(ip_address=ip, defaults={"reason": "AI anomaly detection"})
            return JsonResponse({"status": "blocked", "message": "AI flagged your request as suspicious."}, status=403)
        return None
    def get_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')