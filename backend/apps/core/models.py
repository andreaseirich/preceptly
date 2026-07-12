from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    """Extension of Django User model with subscription tier."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        help_text=_("Associated Django user"),
    )
    SUBSCRIPTION_TIER_CHOICES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("business", "Business"),
    ]
    subscription_tier = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_TIER_CHOICES,
        default="free",
        db_index=True,
        help_text=_("Current subscription tier (free/starter/pro/business)"),
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
        validators=[MinValueValidator(1)],
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
        max_length=255, blank=True, null=True, unique=True, help_text=_("Stripe Subscription ID")
    )
    stripe_price_id = models.CharField(
        max_length=255, blank=True, null=True, help_text=_("Stripe Price ID for current plan")
    )
    subscription_source = models.CharField(
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
    avv_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the user explicitly accepted AGB, AVV, and Datenschutzerklärung."),
    )
    timezone = models.CharField(
        max_length=64,
        default="Europe/Berlin",
        verbose_name="Zeitzone",
    )
    billing_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Name / Firma"),
        help_text=_("Dein vollständiger Name oder Firmenname, der auf Rechnungen erscheint."),
    )
    billing_address = models.TextField(
        blank=True,
        verbose_name=_("Adresse"),
        help_text=_("Straße, PLZ, Ort – wird auf Rechnungen angezeigt."),
    )
    billing_tax_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Steuernummer / USt-IdNr."),
        help_text=_("Deine persönliche Steuernummer oder Umsatzsteuer-ID."),
    )
    billing_email = models.EmailField(
        blank=True,
        verbose_name=_("E-Mail (Rechnungen)"),
        help_text=_("Deine geschäftliche E-Mail-Adresse für Rechnungen."),
    )
    billing_phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_("Telefon"),
        help_text=_("Deine Telefonnummer (optional)."),
    )
    billing_website = models.URLField(
        max_length=200,
        blank=True,
        verbose_name=_("Website"),
        help_text=_("Deine Website (optional, z. B. https://example.de)."),
    )
    billing_bank_iban = models.CharField(
        max_length=34,
        blank=True,
        verbose_name=_("IBAN"),
        help_text=_("Bankverbindung für Rechnungen (optional)."),
    )
    billing_bank_bic = models.CharField(
        max_length=11,
        blank=True,
        verbose_name=_("BIC"),
        help_text=_("BIC/SWIFT deiner Bank (optional)."),
    )
    billing_kleinunternehmer = models.BooleanField(
        default=False,
        verbose_name=_("Kleinunternehmerregelung (§19 UStG)"),
        help_text=_(
            "Aktivieren wenn du die Kleinunternehmerregelung nutzt. Fügt den Hinweis "
            '"Gemäß §19 Abs. 1 UStG wird keine Umsatzsteuer berechnet." zur Rechnung hinzu.'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")

    def __str__(self):
        tier = self.subscription_tier
        tier_str = f" ({tier.capitalize()})" if tier != "free" else ""
        return f"{self.user.username}{tier_str}"


class StripeWebhookEvent(models.Model):
    """Idempotency: track processed webhook events to prevent double-processing."""

    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True, blank=True, help_text=_("Set only after successful processing")
    )
    payload_summary = models.JSONField(default=dict, blank=True)  # minimal, no PII

    class Meta:
        verbose_name = _("Stripe Webhook Event")
        verbose_name_plural = _("Stripe Webhook Events")


class RevocationRequest(models.Model):
    """Revocation (Widerruf) submitted via the e-recht24 revocation button webhook.

    The e-recht24 form is self-reported and NOT identity-verified, so an
    incoming webhook must never cancel a subscription directly. This model
    records the request; the actual cancellation requires the matched user to
    confirm via a tokenized link sent to their account email (two-step flow).
    """

    STATUS_CHOICES = [
        ("pending_confirmation", _("Pending confirmation")),
        ("confirmed_cancelled", _("Confirmed and cancelled")),
        ("no_match", _("No matching account")),
        ("ambiguous_match", _("Ambiguous match")),
        ("expired", _("Confirmation token expired")),
    ]

    revo_id = models.CharField(
        max_length=64,
        unique=True,
        help_text=_("e-recht24 revocation ID (idempotency key for webhook retries)"),
    )
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.CharField(max_length=254, blank=True)
    order_number = models.CharField(max_length=100, blank=True)
    customer_number = models.CharField(max_length=100, blank=True)
    relevant_service = models.CharField(max_length=200, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, db_index=True)
    confirmation_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text=_("Set to None once used or expired so the link cannot be reused"),
    )
    confirmation_token_created_at = models.DateTimeField(null=True, blank=True)
    matched_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revocation_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Revocation Request")
        verbose_name_plural = _("Revocation Requests")

    def __str__(self):
        return f"{self.revo_id} ({self.status})"


class Expense(models.Model):
    """Business expense for tax return (EÜR)."""

    CATEGORY_CHOICES = [
        ("work_materials", _("Work materials")),
        ("travel", _("Travel")),
        ("education", _("Education")),
        ("office", _("Office")),
        ("communication", _("Communication")),
        ("other", _("Other")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    date = models.DateField()
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=300)
    notes = models.TextField(blank=True, null=True)
    business_use_percent = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name=_("Business use (%)"),
        help_text=_("Percentage of this expense used for business purposes (1\u2013100)."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = _("Expense")
        verbose_name_plural = _("Expenses")

    @property
    def effective_amount(self) -> Decimal:
        """Amount after applying business use percentage."""
        return round(self.amount * Decimal(self.business_use_percent) / Decimal("100"), 2)

    def __str__(self):
        return f"{self.date} – {self.description} ({self.amount} €)"


class RequestLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    session_key = models.CharField(max_length=40, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    referer = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["timestamp", "path"])]
