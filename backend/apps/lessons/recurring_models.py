"""
Models for recurring sessions (series appointments).
"""

from apps.contracts.models import Contract
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class RecurringSession(models.Model):
    """Recurring session - template for series appointments."""

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="recurring_sessions",
        help_text=_("Associated contract"),
    )
    start_date = models.DateField(help_text=_("Series start date"))
    end_date = models.DateField(
        null=True, blank=True, help_text=_("Series end date (optional, empty = until contract end)")
    )
    start_time = models.TimeField(help_text=_("Start time"))
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], help_text=_("Duration in minutes")
    )
    travel_time_before_minutes = models.PositiveIntegerField(
        default=0, help_text=_("Travel time before in minutes")
    )
    travel_time_after_minutes = models.PositiveIntegerField(
        default=0, help_text=_("Travel time after in minutes")
    )
    # Recurrence type
    RECURRENCE_TYPE_CHOICES = [
        ("weekly", _("Weekly")),
        ("biweekly", _("Bi-weekly")),
        ("monthly", _("Monthly")),
    ]
    recurrence_type = models.CharField(
        max_length=20,
        choices=RECURRENCE_TYPE_CHOICES,
        default="weekly",
        help_text=_("Recurrence type: Weekly, bi-weekly, or monthly"),
    )
    # Weekdays as Boolean fields
    monday = models.BooleanField(default=False, help_text=_("Monday"))
    tuesday = models.BooleanField(default=False, help_text=_("Tuesday"))
    wednesday = models.BooleanField(default=False, help_text=_("Wednesday"))
    thursday = models.BooleanField(default=False, help_text=_("Thursday"))
    friday = models.BooleanField(default=False, help_text=_("Friday"))
    saturday = models.BooleanField(default=False, help_text=_("Saturday"))
    sunday = models.BooleanField(default=False, help_text=_("Sunday"))
    is_active = models.BooleanField(default=True, help_text=_("Is the series active?"))
    notes = models.TextField(blank=True, null=True, help_text=_("Notes for the series"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "contract"]
        verbose_name = _("Recurring Session")
        verbose_name_plural = _("Recurring Sessions")

    def __str__(self):
        weekdays = self.get_active_weekdays_display()
        return f"{self.contract.student} - {weekdays} {self.start_time} (from {self.start_date})"

    def get_active_weekdays(self):
        """Returns a list of active weekdays (0=Monday, 6=Sunday)."""
        weekdays = []
        if self.monday:
            weekdays.append(0)
        if self.tuesday:
            weekdays.append(1)
        if self.wednesday:
            weekdays.append(2)
        if self.thursday:
            weekdays.append(3)
        if self.friday:
            weekdays.append(4)
        if self.saturday:
            weekdays.append(5)
        if self.sunday:
            weekdays.append(6)
        return weekdays

    def get_active_weekdays_display(self):
        """Returns a human-readable representation of active weekdays."""
        from django.utils.translation import gettext

        weekday_names = [
            gettext("Mo"),
            gettext("Tu"),
            gettext("We"),
            gettext("Th"),
            gettext("Fr"),
            gettext("Sa"),
            gettext("Su"),
        ]
        active = [weekday_names[i] for i in self.get_active_weekdays()]
        return ", ".join(active) if active else gettext("None")


# Alias for backwards compatibility during migration
RecurringLesson = RecurringSession
