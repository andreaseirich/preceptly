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
    travel_policy = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Time-dependent travel policy for on-site booking: enabled, buffer_rules "
            "(weekday, start_time, end_time, buffer_minutes), no_go_windows. Weekday 0=Monday."
        ),
    )
    default_booking_location = models.CharField(
        max_length=20,
        choices=[("online", "Online"), ("vor_ort", "Vor Ort")],
        default="online",
        help_text=_("Default appointment type for public booking; vor_ort applies travel policy."),
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
    stripe_email_last_synced = models.CharField(
        max_length=254,
        blank=True,
        null=True,
        help_text=_("Last email synced to Stripe Customer (skip modify if unchanged)"),
    )
    tutor_no_show_pay_percent = models.PositiveSmallIntegerField(
        default=0,
        help_text=_(
            "TutorSpace, session marked 'tutor did not show (student waited)': share of the "
            "usual lesson amount you still keep. The rest is not paid, and the usual amount "
            "is deducted (net ≈ −(100−this)% of usual pay). 0%% = full deduction (−100%% of "
            "usual pay); 100%% = full usual pay (no deduction)."
        ),
    )
    tutorspace_tier_count_from = models.DateField(
        null=True,
        blank=True,
        help_text=_(
            "TutorSpace pay tiers (13/14 € …): if set, only lessons on or after this date "
            "count toward cumulative hours. Empty = all past TutorSpace lessons count "
            "(can make the preview look ‘too high’ if you have many older sessions)."
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


class StripeWebhookEvent(models.Model):
    """Idempotency: track processed webhook events to prevent double-processing."""

    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    payload_summary = models.JSONField(default=dict, blank=True)  # minimal, no PII

    class Meta:
        verbose_name = _("Stripe Webhook Event")
        verbose_name_plural = _("Stripe Webhook Events")
