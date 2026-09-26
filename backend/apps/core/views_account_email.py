"""E-Mail-Adresse des Tutor-Kontos: nachfragen, wenn sie fehlt, und ändern.

Seit 26.09.2026 braucht jedes Tutor-Konto eine Adresse - für den
Passwort-Reset und damit der Tutor als Verantwortlicher erreichbar ist.
Konten ohne Adresse landen nach dem Login auf EmailRequiredView; solange sie
fehlt, zeigt base.html einen Hinweis (needs_email).

Ändern geht nur mit dem aktuellen Passwort (SettingsView._change_email) und
über einen Bestätigungslink an die neue Adresse: 24 Stunden gültig, nur für
das Konto, das ihn angefordert hat, und nur solange die alte Adresse noch gilt
- dadurch auch nur einmal nutzbar. Danach bekommt die alte Adresse einen
Hinweis. Die Adresse bei Stripe bleibt, wie sie ist (siehe
_maybe_update_stripe_customer_email). Demo- und Portal-Konten sind ausgenommen.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View

from apps.core.background import run_in_background
from apps.core.demo_guard import is_demo_user
from apps.core.forms import UserEmailForm

CHANGE_SALT = "core.account-email-change"
CHANGE_MAX_AGE = 24 * 60 * 60


def needs_email(user) -> bool:
    """Angemeldetes Tutor-Konto ohne E-Mail-Adresse."""
    return bool(
        user is not None
        and user.is_authenticated
        and not user.email
        and not is_demo_user(user)
        and not hasattr(user, "portal_profile")
    )


def mask_email(address: str) -> str:
    """n***@example.com - für den Hinweis an die alte Adresse."""
    local, _at, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _site_url() -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/")


def _safe_next(request) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse("core:dashboard")


def _settings_email_url() -> str:
    return f"{reverse('core:settings')}?section=email"


def _send(label, subject, template, context, recipient):
    run_in_background(
        label,
        send_mail,
        subject=subject,
        message=render_to_string(f"core/email/{template}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=render_to_string(f"core/email/{template}.html", context),
        fail_silently=False,
    )


class EmailRequiredView(LoginRequiredMixin, View):
    """Adresse nachtragen - ohne sie geht es nicht weiter."""

    template_name = "core/email_required.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not needs_email(request.user):
            return redirect(_safe_next(request))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = UserEmailForm(instance=request.user)
        return render(request, self.template_name, {"form": form, "next": _safe_next(request)})

    def post(self, request):
        form = UserEmailForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Email address saved."))
            return redirect(_safe_next(request))
        return render(request, self.template_name, {"form": form, "next": _safe_next(request)})


def request_email_change(request, new_email: str) -> None:
    """Bestätigungslink an die neue Adresse schicken; geändert wird erst beim Klick."""
    user = request.user
    token = signing.dumps({"u": user.pk, "e": new_email, "o": user.email}, salt=CHANGE_SALT)
    context = {
        "username": user.get_username(),
        "confirm_url": _site_url() + reverse("core:email_change_confirm", args=[token]),
        "site_url": _site_url(),
    }
    _send(
        "Bestätigung neue E-Mail-Adresse",
        "Bestätige deine neue E-Mail-Adresse für Preceptly",
        "email_change_confirm",
        context,
        new_email,
    )


class EmailChangeConfirmView(LoginRequiredMixin, View):
    def get(self, request, token):
        try:
            data = signing.loads(token, salt=CHANGE_SALT, max_age=CHANGE_MAX_AGE)
        except signing.BadSignature:  # auch abgelaufen
            data = None
        user = request.user
        if (
            not isinstance(data, dict)
            or data.get("u") != user.pk
            or data.get("o") != user.email
            or is_demo_user(user)
        ):
            messages.error(request, _("This confirmation link is invalid or has expired."))
            return redirect(_settings_email_url())

        old_email = user.email
        user.email = data["e"]
        user.save(update_fields=["email"])
        if old_email:
            _send(
                "Hinweis an alte E-Mail-Adresse",
                "Deine E-Mail-Adresse bei Preceptly wurde geändert",
                "email_changed_notice",
                {
                    "username": user.get_username(),
                    "new_email": mask_email(user.email),
                    "site_url": _site_url(),
                },
                old_email,
            )
        messages.success(request, _("Your email address has been changed."))
        return redirect(_settings_email_url())
