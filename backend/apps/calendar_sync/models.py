"""
Models for two-way CalDAV calendar sync (tutor side) and the mapping/
conflict bookkeeping the sync engine needs.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class CalendarConnection(models.Model):
    """One external calendar a tutor has connected for two-way sync.

    The app-specific password is stored encrypted (apps.calendar_sync.crypto)
    - never in plain text - since it's a real credential for the tutor's
    Apple/Google account, not a Preceptly-scoped token.
    """

    PROVIDER_ICLOUD = "icloud"
    PROVIDER_GOOGLE = "google"
    PROVIDER_CHOICES = [
        (PROVIDER_ICLOUD, "iCloud"),
        (PROVIDER_GOOGLE, "Google"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_connection",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    caldav_url = models.URLField(max_length=500, blank=True)
    caldav_username = models.CharField(max_length=255, blank=True)
    encrypted_password = models.BinaryField(blank=True, null=True)
    sync_enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)
    last_sync_summary = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Counts from the most recent sync run (pushed/pulled/imported/"
            "deleted/conflicts/errors), shown on the settings page so the "
            "tutor can see what actually happened, not just a status dot."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Calendar Connection")
        verbose_name_plural = _("Calendar Connections")

    def __str__(self):
        return f"{self.user} - {self.get_provider_display()}"


class ExternalCalendarEventMapping(models.Model):
    """Links one local object (Session or BlockedTime, via GenericForeignKey
    so both share one mapping table) to its counterpart event in the
    external calendar, plus the last-known-synced timestamps on both sides
    - the sync engine compares current timestamps against these snapshots
    to detect whether either side changed since the last successful sync."""

    connection = models.ForeignKey(
        CalendarConnection, on_delete=models.CASCADE, related_name="event_mappings"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    local_object = GenericForeignKey("content_type", "object_id")

    external_uid = models.CharField(max_length=255)
    external_etag = models.CharField(max_length=255, blank=True)

    local_synced_at = models.DateTimeField(
        help_text=_("Local object's updated_at as of the last successful sync.")
    )
    external_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("External event's last-modified as of the last successful sync."),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("External Calendar Event Mapping")
        verbose_name_plural = _("External Calendar Event Mappings")
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "content_type", "object_id"],
                name="unique_mapping_per_local_object",
            ),
            models.UniqueConstraint(
                fields=["connection", "external_uid"],
                name="unique_mapping_per_external_event",
            ),
        ]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.connection} <-> {self.external_uid}"


class SyncConflict(models.Model):
    """A pending conflict: both the local object and the external event
    changed since the last successful sync, so the sync engine could not
    tell which version should win - the tutor resolves it manually."""

    RESOLUTION_LOCAL = "local"
    RESOLUTION_EXTERNAL = "external"
    RESOLUTION_CHOICES = [
        (RESOLUTION_LOCAL, _("Keep Preceptly version")),
        (RESOLUTION_EXTERNAL, _("Keep external version")),
    ]

    connection = models.ForeignKey(
        CalendarConnection, on_delete=models.CASCADE, related_name="conflicts"
    )
    mapping = models.ForeignKey(
        ExternalCalendarEventMapping, on_delete=models.CASCADE, related_name="conflicts"
    )
    local_snapshot = models.JSONField()
    external_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(max_length=20, choices=RESOLUTION_CHOICES, blank=True)

    class Meta:
        verbose_name = _("Sync Conflict")
        verbose_name_plural = _("Sync Conflicts")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Conflict on {self.mapping} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None
