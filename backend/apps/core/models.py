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
    public_booking_token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Token for public booking URL (e.g. /public-booking/<token>/)"),
    )
    next_invoice_number = models.PositiveIntegerField(
        default=1,
        help_text=_("Next sequential invoice number (Premium only)."),
    )
    # Stripe subscription (source of truth for premium via webhook)
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text=_("Stripe Customer ID"),
    )
    stripe_subscription_id = models.CharField(
        max_length=255, blank=True, null=True, help_text=_("Stripe Subscription ID")
    )
    stripe_price_id = models.CharField(
        max_length=255, blank=True, null=True, help_text=_("Stripe Price ID for current plan")
    )
    premium_source = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=_("Source of premium: 'stripe', 'manual', or null"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")

    def __str__(self):
        premium_str = " (Premium)" if self.is_premium else ""
        return f"{self.user.username}{premium_str}"


class StripeWebhookEvent(models.Model):
    """Idempotency: track processed webhook events to prevent double-processing."""

    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    payload_summary = models.JSONField(default=dict, blank=True)  # minimal, no PII

    class Meta:
        verbose_name = _("Stripe Webhook Event")
        verbose_name_plural = _("Stripe Webhook Events")
