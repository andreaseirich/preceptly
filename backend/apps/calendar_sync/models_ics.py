"""Kalender per Adresse einbinden: Quellen und ihre Zuordnung zu Blockzeiten.

Gedacht für die "geheime Adresse im iCal-Format" von Google Kalender. Die Adresse ist wie ein Passwort und wird
deshalb verschlüsselt gespeichert (derselbe Schlüssel wie beim CalDAV-Passwort). Abruf und Auswertung stehen in
ics_import.py, der Abgleich mit den Blockzeiten in ics_sync.py.
"""

import hashlib

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class IcsCalendarSource(models.Model):
    """Eine Kalenderadresse eines Tutors, aus der Termine als Blockzeiten übernommen werden. Nur lesend."""

    MAX_PER_USER = 5

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ics_sources"
    )
    name = models.CharField(max_length=100, help_text=_("Name shown in the settings."))
    encrypted_url = models.BinaryField(
        help_text=_("The secret address, encrypted. Never shown again.")
    )
    url_hash = models.CharField(
        max_length=64,
        help_text=_("SHA-256 of the address: detects duplicates without decrypting."),
    )
    host = models.CharField(max_length=100, help_text=_("Host of the address, for display only."))
    sync_enabled = models.BooleanField(default=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.CharField(
        max_length=40,
        blank=True,
        help_text=_("Error code of the last attempt (never the address)."),
    )
    last_sync_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Calendar address")
        verbose_name_plural = _("Calendar addresses")
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "url_hash"], name="unique_ics_source_per_user"),
        ]

    def __str__(self):
        return f"{self.user} - {self.name} ({self.host})"

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()


class IcsEventMapping(models.Model):
    """Verbindet einen Termin der Quelle (je Tag) mit der daraus entstandenen Blockzeit.

    blocked_time = NULL heißt: Der Tutor hat die Blockzeit selbst gelöscht. Der Eintrag bleibt als Merkzettel, damit der
    Termin beim nächsten Abgleich nicht neu angelegt wird, solange er in der Quelle steht."""

    source = models.ForeignKey(
        IcsCalendarSource, on_delete=models.CASCADE, related_name="event_mappings"
    )
    key = models.CharField(max_length=300)
    blocked_time = models.OneToOneField(
        "blocked_times.BlockedTime",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ics_mapping",
    )
    occurrence_start = models.DateTimeField()
    content_hash = models.CharField(max_length=64)

    class Meta:
        verbose_name = _("Calendar address appointment")
        verbose_name_plural = _("Calendar address appointments")
        constraints = [
            models.UniqueConstraint(fields=["source", "key"], name="unique_ics_mapping_per_event"),
        ]
        indexes = [models.Index(fields=["source", "occurrence_start"])]

    def __str__(self):
        return f"{self.source_id}: {self.key}"
