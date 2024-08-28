from django.shortcuts import redirect, render
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

def superuser_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a superuser,
    returning a 403 Forbidden response if necessary.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')  # Redirect to login page
        if not request.user.is_superuser:
            return render("portal/notauthorized.html")  # Return a 403 Forbidden response with custom message
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def teacher_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a superuser,
    returning a 403 Forbidden response if necessary.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.usertype == 'Teacher':
            return HttpResponse('Not allowed', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a superuser,
    returning a 403 Forbidden response if necessary.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.usertype == 'Admin':
            return render("portal/notauthorized.html")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def approved_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.approved:
            raise PermissionDenied("You do not have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view