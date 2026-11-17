"""Termine aus einer Kalenderadresse mit den Blockzeiten abgleichen (nur lesend, nur in diese Richtung).

Regeln:

- Zeitraum wie beim CalDAV-Abgleich: 7 Tage zurück, 180 Tage voraus.
- Fehler beim Abrufen oder Auswerten ändern nichts in der Datenbank; sie landen als Fehlercode an der Quelle.
- Übernommen wird nur der Titel (keine Beschreibung, Teilnehmer oder Orte).
- Neu in der Quelle -> neue Blockzeit. Geändert (Titel, Beginn, Ende) -> Blockzeit wird angepasst; eigene Änderungen des
  Tutors bleiben bis dahin stehen. Aus der Quelle verschwunden (im Zeitraum) -> Blockzeit wird gelöscht.
- Hat der Tutor eine importierte Blockzeit selbst gelöscht, wird sie nicht neu angelegt, solange der Termin in der
  Quelle steht (siehe IcsEventMapping).
- Eigene Stunden (UID endet auf @preceptly.de) werden nie importiert; sonst würden sie sich selbst blockieren.
  Stattdessen werden sie mit den echten Stunden verglichen (own_check.py); Abweichungen und fehlende Stunden stehen
  in last_sync_summary["own"]. Es wird nichts geändert: Der Kalender ist nur lesbar.
- Wie beim iCloud-Import gilt keine Tarifgrenze: Der Import spiegelt nur, was im Kalender steht.
"""

import hashlib
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.crypto import CalendarCredentialError, decrypt_password
from apps.calendar_sync.ics_import import IcsError, default_window, fetch_ics, parse_occurrences
from apps.calendar_sync.models import IcsCalendarSource, IcsEventMapping
from apps.calendar_sync.own_check import check_own_lessons

logger = logging.getLogger(__name__)

OWN_UID_SUFFIX = "@preceptly.de"
MIN_INTERVAL = timedelta(
    minutes=15
)  # wie oft eine Quelle abgerufen wird (der Cron läuft alle 5 Minuten)
ERROR_INTERVAL = timedelta(hours=1)  # nach einem Fehler seltener erneut versuchen
MANUAL_COOLDOWN = timedelta(seconds=60)  # Abstand zwischen zwei Klicks auf "Jetzt abgleichen"
# Damit 15 Minuten nicht wegen des 5-Minuten-Takts zu 20 werden:
_DUE_TOLERANCE = timedelta(minutes=1)

EMPTY_SUMMARY = {"created": 0, "updated": 0, "deleted": 0, "skipped": 0}


def _content_hash(occurrence) -> str:
    raw = f"{occurrence.summary}|{occurrence.start.isoformat()}|{occurrence.end.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _record_error(source, code, now):
    source.last_attempt_at = now
    source.last_sync_error = code
    source.save(update_fields=["last_attempt_at", "last_sync_error"])
    return {**EMPTY_SUMMARY, "error": code}


def sync_source(source: IcsCalendarSource, *, data=None, now=None, fetch=None) -> dict:
    """Gleicht eine Quelle ab. data ist die schon abgerufene Datei (beim Hinzufügen), sonst wird abgerufen.

    Gibt die Zahlen zurück (created/updated/deleted/skipped); bei einem Fehler zusätzlich "error" mit dem Fehlercode."""
    now = now or timezone.now()
    fetch = fetch or fetch_ics  # erst hier auflösen, damit sich fetch_ics in Tests ersetzen lässt
    window_start, window_end = default_window(now)
    try:
        if data is None:
            data = fetch(decrypt_password(bytes(source.encrypted_url)))
        occurrences = parse_occurrences(data, window_start, window_end)
    except CalendarCredentialError:
        return _record_error(source, "credential", now)
    except IcsError as error:
        return _record_error(source, error.code, now)

    summary = _apply(source, occurrences, window_start, window_end, now)
    source.last_attempt_at = now
    source.last_synced_at = now
    source.last_sync_error = ""
    source.last_sync_summary = summary
    source.save(
        update_fields=["last_attempt_at", "last_synced_at", "last_sync_error", "last_sync_summary"]
    )
    return summary


@transaction.atomic
def _apply(source, occurrences, window_start, window_end, now) -> dict:
    existing = {m.key: m for m in source.event_mappings.select_related("blocked_time")}
    summary = dict(EMPTY_SUMMARY)
    seen = set()
    own = []  # Termine, die von Preceptly selbst stammen

    for occurrence in occurrences:
        if occurrence.uid.endswith(OWN_UID_SUFFIX):
            summary["skipped"] += 1
            own.append(occurrence)
            continue
        seen.add(occurrence.key)
        digest = _content_hash(occurrence)
        mapping = existing.get(occurrence.key)
        if mapping is None:
            blocked = BlockedTime.objects.create(
                user=source.user,
                title=occurrence.summary,
                start_datetime=occurrence.start,
                end_datetime=occurrence.end,
            )
            IcsEventMapping.objects.create(
                source=source,
                key=occurrence.key,
                blocked_time=blocked,
                occurrence_start=occurrence.start,
                content_hash=digest,
            )
            summary["created"] += 1
        elif mapping.blocked_time_id is None:
            continue  # der Tutor hat sie gelöscht: nicht neu anlegen
        elif mapping.content_hash != digest:
            blocked = mapping.blocked_time
            blocked.title = occurrence.summary
            blocked.start_datetime = occurrence.start
            blocked.end_datetime = occurrence.end
            blocked.save(update_fields=["title", "start_datetime", "end_datetime", "updated_at"])
            mapping.content_hash = digest
            mapping.occurrence_start = occurrence.start
            mapping.save(update_fields=["content_hash", "occurrence_start"])
            summary["updated"] += 1

    for key, mapping in existing.items():
        if key in seen or mapping.occurrence_start > window_end:
            continue  # noch da, oder weiter in der Zukunft, als wir sehen können
        blocked = mapping.blocked_time
        mapping.delete()
        # Termine vor dem Zeitraum bleiben als Vergangenheit stehen; nur der Merkzettel wird aufgeräumt.
        if blocked is not None and mapping.occurrence_start >= window_start:
            blocked.delete()
            summary["deleted"] += 1

    if own:
        try:
            with transaction.atomic():  # ein Fehler hier darf den Import nicht mitreißen
                summary["own"] = check_own_lessons(source.user, own, now, window_end)
        except Exception as error:
            # Nur die Art loggen: Fehlertexte dürfen nie die Adresse enthalten.
            logger.error(
                "Checking own lessons failed for calendar address %s (%s)",
                source.pk,
                type(error).__name__,
            )
    return summary


def _is_due(source, now) -> bool:
    if source.last_attempt_at is None:
        return True
    interval = ERROR_INTERVAL if source.last_sync_error else MIN_INTERVAL
    return now - source.last_attempt_at >= interval - _DUE_TOLERANCE


def sync_all_ics_sources(now=None, fetch=None) -> dict:
    """Gleicht alle fälligen Quellen ab. Einstieg für den Cron (Befehl sync_calendars). Eine fehlerhafte Quelle
    bricht die anderen nicht ab."""
    now = now or timezone.now()
    totals = {"sources": 0, "created": 0, "updated": 0, "deleted": 0, "errors": 0}
    sources = IcsCalendarSource.objects.filter(
        sync_enabled=True, user__is_active=True
    ).select_related("user")
    for source in sources:
        if not _is_due(source, now):
            continue
        totals["sources"] += 1
        try:
            result = sync_source(source, now=now, fetch=fetch)
        except Exception as error:
            # Nur die Art loggen: Fehlertexte dürfen nie die Adresse enthalten.
            logger.error(
                "Unhandled error syncing calendar address %s (%s)", source.pk, type(error).__name__
            )
            totals["errors"] += 1
            continue
        if result.get("error"):
            totals["errors"] += 1
            continue
        for key in ("created", "updated", "deleted"):
            totals[key] += result[key]
    return totals
