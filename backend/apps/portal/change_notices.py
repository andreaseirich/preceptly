"""Was der Tutor erfährt, wenn im Portal ein Termin abgesagt oder verschoben
oder eine Serie beendet wird.

Die Texte entstehen vor dem Löschen bzw. Ändern, weil die Stunde danach nicht
mehr (so) existiert. Versand: email_service.send_change_notification_portal.
"""

from django.utils import translation
from django.utils.formats import date_format

from apps.lessons.booking_origin import TUTOR, account_phrase

WEEKDAYS = [
    ("monday", "Mo"),
    ("tuesday", "Di"),
    ("wednesday", "Mi"),
    ("thursday", "Do"),
    ("friday", "Fr"),
    ("saturday", "Sa"),
    ("sunday", "So"),
]


def _when(date, time, minutes=None) -> str:
    text = f"{date_format(date, 'D, d.m.Y')}, {time.strftime('%H:%M')} Uhr"
    return f"{text} ({minutes} Min.)" if minutes else text


def _actor(portal_user, contract) -> str:
    return "über das Portal " + account_phrase(portal_user.user, contract.user_id, TUTOR)


def cancel_notice(session, portal_user) -> dict:
    contract = session.contract
    name = contract.full_name
    with translation.override("de"):
        when = _when(session.date, session.start_time, session.duration_minutes)
        return {
            "subject": f"Termin abgesagt: {name} — {session.date.strftime('%d.%m.%Y')}",
            "heading": "Termin abgesagt",
            "intro": (
                f"Ein Termin von {name} wurde im Portal abgesagt. Er ist aus deinem Kalender "
                "entfernt und steht beim Schüler unter „Im Portal abgesagte Termine“."
            ),
            "rows": [
                ("Schüler", name),
                ("Termin", when),
                ("Abgesagt", _actor(portal_user, contract)),
            ],
            "push_title": f"Termin abgesagt: {name}",
            "push_body": when,
            "contract_pk": contract.pk,
        }


def reschedule_notice(session, old_date, old_time, portal_user) -> dict:
    """Nach dem Speichern aufrufen: session trägt schon den neuen Termin."""
    contract = session.contract
    name = contract.full_name
    with translation.override("de"):
        old = _when(old_date, old_time)
        new = _when(session.date, session.start_time, session.duration_minutes)
        return {
            "subject": f"Termin verschoben: {name} — {session.date.strftime('%d.%m.%Y')}",
            "heading": "Termin verschoben",
            "intro": f"Ein Termin von {name} wurde im Portal verschoben.",
            "rows": [
                ("Schüler", name),
                ("Bisher", old),
                ("Neu", new),
                ("Verschoben", _actor(portal_user, contract)),
            ],
            "push_title": f"Termin verschoben: {name}",
            "push_body": f"{old} → {new}",
            "contract_pk": contract.pk,
        }


def series_cancel_notice(series, sessions, portal_user) -> dict:
    """sessions: die entfallenden Termine, vor dem Löschen geladen."""
    contract = series.contract
    name = contract.full_name
    days = ", ".join(label for field, label in WEEKDAYS if getattr(series, field))
    with translation.override("de"):
        dates = sorted(s.date for s in sessions)
        if dates:
            dropped = f"{len(dates)} ({date_format(dates[0], 'd.m.Y')} bis {date_format(dates[-1], 'd.m.Y')})"
        else:
            dropped = "keine"
        pattern = f"{days}, {series.start_time.strftime('%H:%M')} Uhr"
        return {
            "subject": f"Serie beendet: {name}",
            "heading": "Serie beendet",
            "intro": (
                f"Eine Serie von {name} wurde im Portal beendet. Die kommenden Termine sind aus "
                "deinem Kalender entfernt und stehen beim Schüler unter „Im Portal abgesagte Termine“."
            ),
            "rows": [
                ("Schüler", name),
                ("Serie", pattern),
                ("Entfallene Termine", dropped),
                ("Beendet", _actor(portal_user, contract)),
            ],
            "push_title": f"Serie beendet: {name}",
            "push_body": f"{pattern} · {len(dates)} Termine entfallen",
            "contract_pk": contract.pk,
        }
