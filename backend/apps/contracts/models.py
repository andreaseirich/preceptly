import json
import secrets

from decimal import Decimal

from apps.students.models import Student
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Contract(models.Model):
    """Contract between tutor and student/institute."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="contracts",
        help_text=_("Student for whom the contract applies"),
    )
    institute = models.CharField(
        max_length=200, blank=True, null=True, help_text=_("Institute name (if applicable)")
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=_("Rate per unit in EUR"),
    )
    unit_duration_minutes = models.PositiveIntegerField(
        default=60, help_text=_("Duration of one unit in minutes")
    )
    start_date = models.DateField(help_text=_("Contract start date"))
    end_date = models.DateField(
        null=True, blank=True, help_text=_("Contract end date (optional, empty = unlimited)")
    )
    is_active = models.BooleanField(default=True, help_text=_("Is the contract active?"))
    has_monthly_planning_limit = models.BooleanField(
        default=True,
        help_text=_(
            "If checked, monthly planning with planned units is required. If unchecked, no maximum number of units is planned."
        ),
    )
    notes = models.TextField(
        blank=True, null=True, help_text=_("Additional notes about the contract")
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
        """Generate booking token if not set."""
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
        unique_together = [["contract", "year", "month"]]
        verbose_name = _("Contract Monthly Plan")
        verbose_name_plural = _("Contract Monthly Plans")

    def __str__(self):
        from django.utils.translation import gettext as _

        return f"{self.contract} - {self.year}-{self.month:02d}: {self.planned_units} {_('units')}"
