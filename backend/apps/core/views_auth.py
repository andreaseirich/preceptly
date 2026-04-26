"""
Authentication views for login, logout, and registration.
"""

import logging

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from apps.core.auth_throttle import throttle_login, throttle_register
from apps.core.forms import RegisterForm
from apps.core.models import UserProfile
from apps.core.utils_booking import ensure_public_booking_token

logger = logging.getLogger(__name__)


class TutorFlowLoginView(LoginView):
    """Custom login view for TutorFlow."""

    template_name = "core/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("core:dashboard")

    def post(self, request, *args, **kwargs):
        throttled = throttle_login(request)
        if throttled:
            return throttled
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        result = super().form_valid(form)
        self.request.session.cycle_key()
        return result

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

    def post(self, request, *args, **kwargs):
        throttled = throttle_register(request)
        if throttled:
            return throttled
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"is_premium": False})
        ensure_public_booking_token(profile)
        login(self.request, user)
        self._notify_admin(user)
        return redirect(self.success_url)

    def _notify_admin(self, user) -> None:
        recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
        if not recipient:
            return
        body = "Ein neuer Nutzer hat sich registriert.\n\n"
        body += f"Benutzername: {user.username}\n"
        body += f"E-Mail: {user.email or '(keine Angabe)'}\n"
        try:
            send_mail(
                subject=f"[TutorFlow] Neue Registrierung: {user.username}",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Registration notification email failed for user %s", user.username)
