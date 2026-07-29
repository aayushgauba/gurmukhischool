from django.shortcuts import redirect, render
from django.core.exceptions import PermissionDenied
from functools import wraps


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if not request.user.has_role(*roles):
                raise PermissionDenied("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator

def superuser_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a superuser,
    returning a 403 Forbidden response if necessary.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')  # Redirect to login page
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have permission to access this page.")  # Return a 403 Forbidden response with custom message
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def teacher_required(view_func):
    return role_required("Teacher")(view_func)

def admin_required(view_func):
    return role_required("Admin")(view_func)


def web_manager_required(view_func):
    return role_required("WebManager", "Admin")(view_func)

def emailSender_required(view_func):
    return role_required("Admin", "EmailSender")(view_func)

def approved_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.approved:
            return render(request, "portal/notauthorized.html")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
