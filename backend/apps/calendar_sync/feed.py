"""Kalender-Abo für Tutoren: baut die iCal-Datei mit den Stunden eines Tutors (nur lesend).

Der Abo-Link funktioniert in Google Kalender, iCloud und Outlook. Enthalten sind je Stunde nur Titel und Zeit, keine
Notizen, keine Hausaufgaben, kein Meeting-Link. Fahrzeiten sind nicht enthalten: Das Abo zeigt die Unterrichtszeit, nicht
die Blockzeit mit Anfahrt, die der iCloud-Abgleich schreibt.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone
from icalendar import Calendar, Event

from apps.lessons.models import Session

FEED_WINDOW_PAST_DAYS = 30
FEED_WINDOW_FUTURE_DAYS = 365
FEED_STATUSES = ("planned", "taught", "paid")
NEUTRAL_TITLE = "Nachhilfe"
NAMED_TITLE = "Nachhilfe - {student}"


def _tutor_timezone(user):
    name = getattr(getattr(user, "profile", None), "timezone", "") or settings.TIME_ZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(settings.TIME_ZONE)


def session_title(session, include_student_names):
    if not include_student_names:
        return NEUTRAL_TITLE
    contract = session.contract
    student = f"{contract.first_name} {contract.last_name}".strip()
    return NAMED_TITLE.format(student=student) if student else NEUTRAL_TITLE


def build_feed(feed, now=None) -> bytes:
    """Die Datei für einen TutorCalendarFeed."""
    now = now or timezone.now()
    tutor_tz = _tutor_timezone(feed.user)
    today = now.astimezone(tutor_tz).date()
    sessions = (
        Session.objects.filter(
            contract__user=feed.user,
            status__in=FEED_STATUSES,
            date__gte=today - timedelta(days=FEED_WINDOW_PAST_DAYS),
            date__lte=today + timedelta(days=FEED_WINDOW_FUTURE_DAYS),
        )
        .select_related("contract")
        .order_by("date", "start_time", "pk")
    )

    calendar = Calendar()
    calendar.add("prodid", "-//Preceptly//Tutor Calendar Feed//DE")
    calendar.add("version", "2.0")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", "Preceptly Nachhilfe")
    calendar.add("x-published-ttl", "PT1H")
    calendar.add("refresh-interval", timedelta(hours=1), parameters={"VALUE": "DURATION"})

    for session in sessions:
        start = datetime.combine(session.date, session.start_time, tzinfo=tutor_tz)
        event = Event()
        event.add("uid", f"preceptly-tutor-session-{session.pk}@preceptly.de")
        event.add("summary", session_title(session, feed.include_student_names))
        event.add("dtstart", start)
        event.add("dtend", start + timedelta(minutes=session.duration_minutes))
        event.add("dtstamp", now)
        event.add("last-modified", session.updated_at)
        event.add("status", "CONFIRMED")
        calendar.add_component(event)

    return calendar.to_ical()
