"""Kontrolle der eigenen Termine in einem verbundenen Kalender.

Termine, die von Preceptly selbst stammen (Kennung `preceptly-session-<Nr>@preceptly.de`, auch `-tutor-` und `-portal-`),
werden nie als Blockzeit übernommen: Sonst würden sich die Stunden selbst blockieren. Stattdessen werden sie mit den echten
Stunden verglichen, und Preceptly meldet, was nicht übereinstimmt. Es wird nichts geändert: Der Kalender ist nur lesbar, und
Preceptly bleibt die Quelle der Wahrheit für die Stunden (an ihnen hängen Rechnungen und Steuern).

Gemeldet wird in drei Gruppen:

- **changed:** Die Stunde gibt es, aber der Termin im Kalender hat eine andere Zeit. Als richtig gelten die reine
  Unterrichtszeit (Abo-Link) und der Zeitblock mit Fahrzeiten (iCloud-Abgleich).
- **gone:** Zu dem Termin gibt es bei diesem Tutor keine Stunde mehr (gelöscht, abgesagt oder eine fremde/unbekannte
  Kennung). Für fremde Stunden wird nichts Inhaltliches preisgegeben: Es steht nur die Zeit des Termins im Kalender.
- **missing:** Eine künftige Stunde fehlt im Kalender. Das wird nur gemeldet, wenn der Kalender überhaupt eigene Termine
  enthält (sonst ist er keine Kopie der Stunden), und nur für künftige Stunden (der iCloud-Abgleich entfernt vergangene).
"""

import re
from datetime import datetime, timedelta

from apps.calendar_sync.feed import _tutor_timezone
from apps.lessons.models import Session

OWN_UID = re.compile(r"^preceptly-(?:tutor-|portal-)?session-(\d+)@preceptly\.de$")
CHECKED_STATUSES = ("planned", "taught", "paid")
MAX_DETAILS = (
    10  # so viele Zeiten je Gruppe werden mitgespeichert; die Zahlen sind immer vollständig
)


def _label(moment, tz):
    return moment.astimezone(tz).strftime("%d.%m. %H:%M")


def _lesson_start(lesson, tz):
    return datetime.combine(lesson.date, lesson.start_time, tzinfo=tz)


def check_own_lessons(user, own_occurrences, now, window_end) -> dict:
    """Vergleicht die eigenen Termine eines Kalenders mit den Stunden von user. Gibt Zahlen und die ersten Zeiten zurück."""
    tz = _tutor_timezone(user)
    lesson_ids = {}
    for occurrence in own_occurrences:
        match = OWN_UID.match(occurrence.uid)
        lesson_ids[occurrence.key] = int(match.group(1)) if match else None

    lessons = {
        lesson.pk: lesson
        for lesson in Session.objects.filter(
            pk__in=[pk for pk in lesson_ids.values() if pk], contract__user=user
        )
    }

    ok = 0
    changed, gone, matched = [], [], set()
    for occurrence in own_occurrences:
        lesson = lessons.get(lesson_ids[occurrence.key])
        if lesson is None or lesson.status == "cancelled":
            gone.append({"label": _label(occurrence.start, tz)})
            continue
        matched.add(lesson.pk)
        start = _lesson_start(lesson, tz)
        plain_end = start + timedelta(minutes=lesson.duration_minutes)
        accepted = (
            (start, plain_end),
            (
                start - timedelta(minutes=lesson.travel_time_before_minutes),
                plain_end + timedelta(minutes=lesson.travel_time_after_minutes),
            ),
        )
        if (occurrence.start, occurrence.end) in accepted:
            ok += 1
        else:
            changed.append({"label": _label(start, tz), "lesson": lesson.pk})

    missing = []
    if own_occurrences:
        today = now.astimezone(tz).date()
        last_day = (window_end - timedelta(days=1)).astimezone(tz).date()
        upcoming = (
            Session.objects.filter(
                contract__user=user,
                status__in=CHECKED_STATUSES,
                date__gte=today,
                date__lte=last_day,
            )
            .exclude(pk__in=matched)
            .order_by("date", "start_time", "pk")
        )
        for lesson in upcoming:
            start = _lesson_start(lesson, tz)
            if start + timedelta(minutes=lesson.duration_minutes) <= now:
                continue  # schon vorbei: der iCloud-Abgleich entfernt solche Termine bewusst
            missing.append({"label": _label(start, tz), "lesson": lesson.pk})

    return {
        "found": len(own_occurrences),
        "ok": ok,
        "changed": len(changed),
        "gone": len(gone),
        "missing": len(missing),
        "details": {
            "changed": changed[:MAX_DETAILS],
            "gone": gone[:MAX_DETAILS],
            "missing": missing[:MAX_DETAILS],
        },
    }
