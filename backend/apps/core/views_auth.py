"""
Authentication views for login and logout.
"""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy


class TutorFlowLoginView(LoginView):
    """Custom login view for TutorFlow."""

    template_name = "core/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("core:dashboard")


class TutorFlowLogoutView(LogoutView):
    """Custom logout view for TutorFlow."""

    next_page = reverse_lazy("core:login")
