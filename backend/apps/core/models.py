from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    """Extension of Django User model with Premium flag."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        help_text=_("Associated Django user"),
    )
    is_premium = models.BooleanField(
        default=False, help_text=_("Does the user have premium access?")
    )
    premium_since = models.DateTimeField(
        null=True, blank=True, help_text=_("Since when is the user a premium member?")
    )
    default_working_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Default working hours for booking pages (format: {'monday': [{'start': '09:00', 'end': '17:00'}], ...}). Used as fallback when contract has no working_hours."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")

    def __str__(self):
        premium_str = " (Premium)" if self.is_premium else ""
        return f"{self.user.username}{premium_str}"
