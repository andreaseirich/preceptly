"""
Models for recurring blocked times (series appointments).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class RecurringBlockedTime(models.Model):
    """Recurring blocked time - template for series appointments."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_blocked_times",
        help_text=_("User who owns this recurring blocked time"),
    )
    title = models.CharField(
        max_length=200,
        help_text=_("Title of the blocked time (e.g., 'University lecture', 'Community')"),
    )
    description = models.TextField(
        blank=True, null=True, help_text=_("Description of the blocked time")
    )
    start_date = models.DateField(help_text=_("Series start date"))
    end_date = models.DateField(null=True, blank=True, help_text=_("Series end date (optional)"))
    start_time = models.TimeField(help_text=_("Start time"))
    end_time = models.TimeField(help_text=_("End time"))
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "title"]
        verbose_name = _("Recurring Blocked Time")
        verbose_name_plural = _("Recurring Blocked Times")

    def __str__(self):
        weekdays = self.get_active_weekdays_display()
        return f"{self.title} - {weekdays} {self.start_time} (from {self.start_date})"

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
        from django.utils.translation import gettext_lazy as _

        weekday_names = [_("Mo"), _("Tu"), _("We"), _("Th"), _("Fr"), _("Sa"), _("Su")]
        active = [str(weekday_names[i]) for i in self.get_active_weekdays()]
        return ", ".join(active) if active else str(_("None"))
