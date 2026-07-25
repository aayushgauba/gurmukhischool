from django.http import JsonResponse
from django.db import DatabaseError

from .models import BlacklistedIP


class IPBlockMiddleware:
    """Reject requests from IP addresses explicitly stored in the blocklist."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip_address = request.META.get("REMOTE_ADDR")
        if ip_address:
            try:
                blocked = BlacklistedIP.objects.filter(
                    ip_address=ip_address
                ).exists()
            except DatabaseError:
                # Allow Django management and initial migration requests to start.
                blocked = False

            if blocked:
                return JsonResponse(
                    {"detail": "Your IP address has been blocked."},
                    status=403,
                )

        return self.get_response(request)
