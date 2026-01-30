from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# Import RecurringBlockedTime für Django-Erkennung


class BlockedTime(models.Model):
    """Personal appointments/blocked times (e.g., university, job, community)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_times",
        help_text=_("User who owns this blocked time"),
    )
    title = models.CharField(
        max_length=200,
        help_text=_("Title of the blocked time (e.g., 'University lecture', 'Community')"),
    )
    description = models.TextField(
        blank=True, null=True, help_text=_("Description of the blocked time")
    )
    start_datetime = models.DateTimeField(help_text=_("Start datetime"))
    end_datetime = models.DateTimeField(help_text=_("End datetime"))
    is_recurring = models.BooleanField(
        default=False, help_text=_("Is this a recurring blocked time?")
    )
    recurring_pattern = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Recurrence pattern (e.g., 'weekly', 'daily') - for future extension"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_datetime"]
        verbose_name = _("Blocked Time")
        verbose_name_plural = _("Blocked Times")
        indexes = [
            models.Index(fields=["start_datetime", "end_datetime"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.start_datetime.strftime('%Y-%m-%d %H:%M')}"
