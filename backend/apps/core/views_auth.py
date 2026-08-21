"""
Authentication views for login, logout, and registration.
"""

import logging
import re
import unicodedata

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView

from apps.core.auth_throttle import (
    _cache_key,
    throttle_login,
    throttle_register,
)
from apps.core.forms import RegisterForm
from apps.core.models import UserProfile
from apps.core.referrals import ensure_referral_code, resolve_referrer_user
from apps.core.utils_booking import ensure_public_booking_token

logger = logging.getLogger(__name__)


class TutorFlowLoginView(LoginView):
    """Custom login view for Preceptly."""

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
        # Throttle-Zähler nach erfolgreichem Login zurücksetzen
        user = form.get_user()
        uname = unicodedata.normalize("NFKC", user.get_username()).casefold()[:64]
        cache.delete(_cache_key("login_user", uname) + ":count")
        cache.delete(_cache_key("login_user", uname) + ":meta")
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add landing page link for non-authenticated users
        context["show_landing_link"] = not self.request.user.is_authenticated
        return context


class TutorFlowLogoutView(LogoutView):
    """Custom logout view for Preceptly."""

    next_page = reverse_lazy("core:login")


class RegisterView(CreateView):
    """Registration view for new tutor accounts. New users are non-premium."""

    form_class = RegisterForm
    template_name = "core/register.html"
    success_url = reverse_lazy("core:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        ref_code = request.GET.get("ref") or request.POST.get("ref")
        if ref_code:
            request.session["referral_code"] = ref_code.strip().upper()[:12]
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        throttled = throttle_register(request)
        if throttled:
            return throttled
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()
                avv_consent = self.request.POST.get("avv_consent")
                profile, _ = UserProfile.objects.get_or_create(user=user, defaults={})
                if avv_consent and not profile.avv_accepted_at:
                    profile.avv_accepted_at = timezone.now()
                    profile.save(update_fields=["avv_accepted_at"])
                ensure_public_booking_token(profile)
                ensure_referral_code(profile)
                ref_code = self.request.session.pop("referral_code", None)
                referrer = resolve_referrer_user(ref_code)
                if referrer and referrer.pk != user.pk:
                    profile.referred_by = referrer
                    profile.save(update_fields=["referred_by"])
        except IntegrityError:
            form.add_error(None, _("Registration failed. Please try again."))
            return self.form_invalid(form)
        login(self.request, user)
        self.request.session.cycle_key()
        self._notify_admin(user)
        return redirect(self.success_url)

    def _notify_admin(self, user) -> None:
        recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
        if not recipient:
            return
        safe_username = re.sub(r"[\r\n\x00-\x1f]", "", user.username)[:200]
        safe_email = re.sub(r"[\r\n\x00-\x1f]", "", user.email or "")[:200]
        context = {
            "username": safe_username,
            "email": safe_email,
            "has_email": bool(safe_email),
            "site_url": getattr(settings, "SITE_URL", ""),
        }
        html_message = render_to_string("core/email/registration_notification.html", context)
        plain_message = render_to_string("core/email/registration_notification.txt", context)
        try:
            send_mail(
                subject=f"[Preceptly] Neue Registrierung: {safe_username}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception:
            logger.exception(
                "Registration notification email failed for user %s",
                safe_username,
            )
