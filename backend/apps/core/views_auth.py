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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add landing page link for non-authenticated users
        context["show_landing_link"] = not self.request.user.is_authenticated
        return context


class TutorFlowLogoutView(LogoutView):
    """Custom logout view for TutorFlow."""

    next_page = reverse_lazy("core:login")
