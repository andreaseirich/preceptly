"""Tageszähler ohne personenbezogene Daten (siehe DailyCounter).

Der Zähler steht für Dinge, die man sonst nirgends sieht, etwa Registrierungen, die der Honeypot abgewiesen hat
(RegisterView.form_invalid). Gezählt wird nach dem Berliner Kalendertag."""

from datetime import timedelta

from django.db.models import F, Sum
from django.utils import timezone

from apps.core.models import DailyCounter

# Namen der Zähler. Kurz halten (max. 50 Zeichen).
REGISTRATION_HONEYPOT = "registration_honeypot"


def count_event(name, day=None):
    """Zählt ein Ereignis für den Tag (heute, wenn nicht angegeben) um eins hoch.

    get_or_create ist bei gleichzeitigen Aufrufen sicher (die eindeutige Bedingung fängt das Anlegen doppelt ab); das
    Hochzählen selbst läuft in der Datenbank (F), damit parallele Aufrufe sich nicht überschreiben."""
    day = day or timezone.localdate()
    counter, created = DailyCounter.objects.get_or_create(name=name, day=day, defaults={"count": 1})
    if not created:
        DailyCounter.objects.filter(pk=counter.pk).update(count=F("count") + 1)


def counts_by_day(name, days):
    """Die letzten `days` Tage als [{"day": date, "count": n}], älteste zuerst, Tage ohne Ereignis mit 0."""
    today = timezone.localdate()
    first = today - timedelta(days=days - 1)
    found = dict(
        DailyCounter.objects.filter(name=name, day__gte=first, day__lte=today).values_list(
            "day", "count"
        )
    )
    return [
        {
            "day": first + timedelta(days=offset),
            "count": found.get(first + timedelta(days=offset), 0),
        }
        for offset in range(days)
    ]


def total_count(name):
    """Summe über alle Tage, seit der Zähler läuft."""
    return DailyCounter.objects.filter(name=name).aggregate(total=Sum("count"))["total"] or 0
