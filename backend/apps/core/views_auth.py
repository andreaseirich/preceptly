"""
Authentication views for login, logout, and registration.
"""

from apps.core.forms import RegisterForm
from apps.core.models import UserProfile
from apps.core.utils_booking import ensure_public_booking_token
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView


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


class RegisterView(CreateView):
    """Registration view for new tutor accounts. New users are non-premium."""

    form_class = RegisterForm
    template_name = "core/register.html"
    success_url = reverse_lazy("core:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"is_premium": False})
        ensure_public_booking_token(profile)
        login(self.request, user)
        return redirect(self.success_url)
