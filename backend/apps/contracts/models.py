import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.students.models import Student


class Contract(models.Model):
    """Contract between tutor and student/institute."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="contracts",
        verbose_name=_("student"),
        help_text=_("Student for whom the contract applies"),
    )
    institute = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("institute"),
        help_text=_("Institute name (if applicable)"),
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("hourly rate"),
        help_text=_("Rate per unit in EUR"),
    )
    unit_duration_minutes = models.PositiveIntegerField(
        default=60,
        verbose_name=_("unit duration (minutes)"),
        help_text=_("Duration of one unit in minutes"),
    )
    start_date = models.DateField(
        verbose_name=_("start date"),
        help_text=_("Contract start date"),
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("end date"),
        help_text=_("Contract end date (optional, empty = unlimited)"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("active"),
        help_text=_("Is the contract active?"),
    )
    has_monthly_planning_limit = models.BooleanField(
        default=True,
        verbose_name=_("monthly planning limit"),
        help_text=_(
            "If checked, monthly planning with planned units is required. If unchecked, no maximum number of units is planned."
        ),
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("notes"),
        help_text=_("Additional notes about the contract"),
    )
    booking_token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Token for external booking link (auto-generated if empty)"),
    )
    working_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Working hours for booking page (format: {'monday': [{'start': '09:00', 'end': '17:00'}], ...})"
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "student"]
        verbose_name = _("Contract")
        verbose_name_plural = _("Contracts")

    def save(self, *args, **kwargs):
        """Generate booking token if not set. When deactivating, delete future lessons."""
        if self.pk:
            old = Contract.objects.filter(pk=self.pk).first()
            if old and old.is_active and not self.is_active:
                from apps.lessons.models import Lesson

                today = timezone.localdate()
                Lesson.objects.filter(contract=self, date__gte=today).delete()
        if not self.booking_token:
            self.booking_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        from django.utils.translation import gettext as _

        institute_str = f" ({self.institute})" if self.institute else ""
        return f"{self.student} - {self.hourly_rate}€/{_('unit')}{institute_str}"


class ContractMonthlyPlan(models.Model):
    """Monthly planning for a contract - explicit planned units per month."""

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="monthly_plans",
        help_text=_("Associated contract"),
    )
    year = models.PositiveIntegerField(help_text=_("Year"))
    month = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], help_text=_("Month (1-12)")
    )
    planned_units = models.PositiveIntegerField(
        default=0, help_text=_("Planned units for this month")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year", "month"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "year", "month"],
                name="unique_contract_year_month",
            )
        ]
        verbose_name = _("Contract Monthly Plan")
        verbose_name_plural = _("Contract Monthly Plans")

    def __str__(self):
        from django.utils.translation import gettext as _

        return f"{self.contract} - {self.year}-{self.month:02d}: {self.planned_units} {_('units')}"


class InstituteTierConfig(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="institute_tier_configs",
        verbose_name=_("user"),
    )
    institute_name = models.CharField(max_length=200, verbose_name=_("institute name"))
    tiers = models.JSONField(
        default=list,
        verbose_name=_("tiers"),
        help_text=_(
            'List of dicts: [{"hours_from": 0, "label": "13 €/h"}, ...], sorted by hours_from ascending'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "institute_name")]
        ordering = ["institute_name"]
        verbose_name = _("Institute tier config")
        verbose_name_plural = _("Institute tier configs")

    def __str__(self):
        return f"{self.institute_name} ({self.user.username})"
