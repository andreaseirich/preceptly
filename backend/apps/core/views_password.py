"""„Passwort vergessen" für Tutoren.

Baut auf Djangos Passwort-Reset auf, mit drei Abweichungen:

- Nur Tutor-Konten. Schüler und Eltern haben ihren eigenen Reset im Portal,
  die öffentlichen Demo-Konten werden nie zurückgesetzt.
- Die Mail geht im Hintergrund raus (apps/core/background.py). So antwortet
  die Seite gleich schnell, egal ob es zur Adresse ein Konto gibt.
- Höchstens 5 Anfragen pro Minute und IP.

Der Link gilt PASSWORD_RESET_TIMEOUT (1 Stunde) und nur einmal: Mit dem neuen
Passwort ändert sich dessen Hash, der Token passt dann nicht mehr, und Django
meldet alle anderen Sitzungen ab. Die Mail nennt auch den Benutzernamen -
Tutoren melden sich damit an, nicht mit der E-Mail-Adresse.
"""

import unicodedata

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from apps.core.auth_throttle import _cache_key
from apps.core.background import run_in_background
from apps.core.demo_guard import DEMO_USERNAMES


def is_tutor_account(user) -> bool:
    """Weder Demo- noch Portal-Konto."""
    return user.username not in DEMO_USERNAMES and not hasattr(user, "portal_profile")


class TutorPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        return (user for user in super().get_users(email) if is_tutor_account(user))

    def send_mail(self, *args, **kwargs):
        run_in_background("Tutor-Passwort-Reset", super().send_mail, *args, **kwargs)


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="post")
class TutorPasswordResetView(auth_views.PasswordResetView):
    form_class = TutorPasswordResetForm
    template_name = "core/password_reset_form.html"
    subject_template_name = "core/email/password_reset_subject.txt"
    email_template_name = "core/email/password_reset.txt"
    html_email_template_name = "core/email/password_reset.html"
    success_url = reverse_lazy("core:password_reset_done")

    @property
    def extra_email_context(self):
        return {"site_url": getattr(settings, "SITE_URL", "").rstrip("/")}


class TutorPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "core/password_reset_done.html"


class TutorPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "core/password_reset_confirm.html"
    success_url = reverse_lazy("core:password_reset_complete")

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user is not None and is_tutor_account(user) else None

    def form_valid(self, form):
        response = super().form_valid(form)
        # Wer sich mit Fehlversuchen ausgesperrt hat, soll gleich wieder rein.
        uname = unicodedata.normalize("NFKC", form.user.get_username()).casefold()[:64]
        cache.delete(_cache_key("login_user", uname) + ":count")
        cache.delete(_cache_key("login_user", uname) + ":meta")
        return response


class TutorPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "core/password_reset_complete.html"
