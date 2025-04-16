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
        status_code = 200
        response_time = 0.0
        request_data.append((now, path, status_code, response_time))
        new_data = []
        for (ts, p, st, rt) in request_data:
            if now - ts < self.WINDOW_SECONDS:
                new_data.append((ts, p, st, rt))
        cache.set(key, new_data, timeout=self.WINDOW_SECONDS)
        total_requests = len(new_data)
        if total_requests < 5:
            return None
        ratio_404 = sum(1 for (ts, p, st, rt) in new_data if st == 404) / total_requests
        suspicious_hits = 0
        for (ts, p, st, rt) in new_data:
            p_lower = p.lower()
            if any(kw in p_lower for kw in malicious_keywords):
                suspicious_hits += 1
        avg_rt = np.mean([rt for (ts, p, st, rt) in new_data]) if new_data else 0
        sorted_data = sorted(new_data, key=lambda x: x[0])
        intervals = []
        for i in range(1, len(sorted_data)):
            intervals.append(sorted_data[i][0] - sorted_data[i-1][0])
        avg_interval = np.mean(intervals) if intervals else 0
        X = np.array([[total_requests, ratio_404, suspicious_hits, avg_rt, avg_interval]], dtype=float)
        pred = model.predict(X)[0]  # => 1 or -1
        if pred == -1:
            BlacklistedIP.objects.get_or_create(ip_address=ip, defaults={"reason": "AI anomaly detection"})
            return JsonResponse({"status": "blocked", "message": "IsolationForest flagged you as suspicious."}, status=403)
        return None

    def get_ip(self, request):
        """Extract IP from X-Forwarded-For or REMOTE_ADDR"""
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')