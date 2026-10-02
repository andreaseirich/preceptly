"""Im Portal abgesagte Termine - ein Archiv, getrennt von den Stunden.

Eine Absage im Portal entfernt die Stunde aus dem Kalender. Bis 02.10.2026 war
sie damit spurlos weg: Niemand konnte nachsehen, wer wann abgesagt hatte.

Die Stunde bleibt bewusst nicht mit Status „abgesagt“ stehen. Viele Abfragen
(Konflikte, Kennzahlen, Kalender-Sync, Portal-Kalender) filtern nicht nach
Status und würden sie weiter wie einen Termin behandeln.
"""

from django.conf import settings
from django.db import models

from apps.contracts.models import Contract


class CancelledSession(models.Model):
    VIA_PORTAL = "portal"
    VIA_PORTAL_SERIES = "portal_series"

    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name="cancelled_sessions"
    )
    date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()
    notes = models.TextField(blank=True, default="")
    was_series = models.BooleanField(default=False)
    # Herkunft der Stunde, übernommen aus Session (booking_origin.py)
    booked_at = models.DateTimeField(null=True, blank=True)
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_via = models.CharField(max_length=20, blank=True, null=True)
    cancelled_at = models.DateTimeField(auto_now_add=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancelled_via = models.CharField(
        max_length=20,
        choices=[(VIA_PORTAL, "Portal"), (VIA_PORTAL_SERIES, "Portal (ganze Serie)")],
    )

    class Meta:
        ordering = ["-cancelled_at", "-date", "-start_time"]
        indexes = [
            models.Index(fields=["contract", "-cancelled_at"], name="lessons_canc_contract_idx")
        ]

    def __str__(self):
        return f"{self.contract} - {self.date} {self.start_time} (abgesagt)"
