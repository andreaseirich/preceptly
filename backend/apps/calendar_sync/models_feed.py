"""Kalender-Abo für Tutoren: ein geheimer Link, über den Google Kalender, iCloud oder Outlook die Stunden abrufen."""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TutorCalendarFeed(models.Model):
    """Der Abo-Link eines Tutors. Der Token in der Adresse ist die Berechtigung (wie beim Portal-Feed); wird er
    erneuert, ist der alte Link sofort ungültig. Wird der Eintrag gelöscht, gibt es keinen Link mehr."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_feed"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    include_student_names = models.BooleanField(
        default=False,
        help_text=_(
            "Put the student's name in the title of each appointment. Off by default: the link is not a login."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Calendar subscription")
        verbose_name_plural = _("Calendar subscriptions")

    def __str__(self):
        return f"{self.user} - feed"
