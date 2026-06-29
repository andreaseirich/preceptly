import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Contract(models.Model):
    """Vertrag zwischen Tutor und Schüler (enthält alle Schülerdaten)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contracts",
        verbose_name=_("tutor"),
        help_text=_("Tutor who owns this contract"),
    )
    first_name = models.CharField(max_length=100, verbose_name=_("first name"))
    last_name = models.CharField(max_length=100, verbose_name=_("last name"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("Schüler-E-Mail"))
    parent_email = models.EmailField(blank=True, null=True, verbose_name=_("Eltern-E-Mail"))
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("phone"))
    school = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("school"))
    grade = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("grade"))
    subjects = models.CharField(max_length=500, blank=True, null=True, verbose_name=_("subjects"))
    is_adult = models.BooleanField(
        default=False,
        verbose_name=_("Erwachsener Schüler"),
        help_text=_("Wenn aktiviert, wird kein Eltern-Portal-Zugang angeboten."),
    )
    booking_code_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("SHA-256 hash of the public booking code (never store plaintext)"),
    )
    institute = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("institute"))
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("hourly rate"),
    )
    unit_duration_minutes = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        verbose_name=_("unit duration (minutes)"),
    )
    start_date = models.DateField(verbose_name=_("start date"))
    end_date = models.DateField(null=True, blank=True, verbose_name=_("end date"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("active"))
    has_monthly_planning_limit = models.BooleanField(
        default=True,
        verbose_name=_("monthly planning limit"),
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_("notes"))
    booking_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    working_hours = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "last_name", "first_name"]
        verbose_name = _("Schüler")
        verbose_name_plural = _("Schüler")

    def save(self, *args, **kwargs):
        if self.pk:
            with transaction.atomic():
                old = Contract.objects.select_for_update().filter(pk=self.pk).first()
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
        return f"{self.full_name} - {self.hourly_rate}€/{_('unit')}{institute_str}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def student(self):
        """Rückwärtskompatibilität: gibt self zurück."""
        return self


class ContractMonthlyPlan(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="monthly_plans")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    planned_units = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year", "month"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "year", "month"], name="unique_contract_year_month"
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
    )
    institute_name = models.CharField(max_length=200)
    tiers = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "institute_name")]
        ordering = ["institute_name"]
        verbose_name = _("Institute tier config")
        verbose_name_plural = _("Institute tier configs")

    def __str__(self):
        return f"{self.institute_name} ({self.user.username})"
