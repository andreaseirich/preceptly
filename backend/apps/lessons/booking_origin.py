"""Wann und von wem eine Stunde gebucht oder abgesagt wurde - für die Anzeige.

Seit 29.09.2026 merkt sich jede neue Stunde das buchende Konto
(Session.booked_by) und den Weg (Session.created_via). Ältere Stunden kennen
nur den Zeitpunkt und, bei Einzelbuchungen im Portal, den Weg. Anlass: Ein
Schüler bestritt eine Portal-Buchung, und niemand konnte nachsehen, welches
Konto sie angelegt hatte.

Seit 02.10.2026 kommen die im Portal abgesagten Termine dazu
(CancelledSession, siehe cancelled_models.py).
"""

from dataclasses import dataclass
from datetime import datetime

from django.utils.translation import gettext as _

TUTOR = "tutor"
PORTAL = "portal"


@dataclass(frozen=True)
class BookingOrigin:
    at: datetime
    how: str  # Weg und Konto, z. B. „über das Portal vom Schülerkonto“; leer, wenn unbekannt
    note: str  # Hinweis, falls das Konto fehlt


@dataclass(frozen=True)
class CancellationInfo:
    cancelled_at: datetime
    cancelled_how: str
    booked: BookingOrigin | None


def _channel(created_via, in_series) -> str:
    if created_via == "portal_booking":
        return _("via the portal")
    if created_via == "portal_series":
        return _("as a series via the portal")
    if in_series:
        return _("as part of a series")
    return ""


def account_phrase(user, tutor_id, viewer, portal_user=None) -> str:
    """„von dir“, „vom Schülerkonto (…)“ usw. tutor_id: der Tutor des Vertrags.
    viewer: TUTOR oder PORTAL; portal_user: das angemeldete Portal-Konto."""
    if user is None:
        return ""
    if viewer == PORTAL and portal_user is not None and user.pk == portal_user.user_id:
        return _("by you")
    if user.pk == tutor_id:
        if viewer == TUTOR:
            return _("by you")
        name = user.get_full_name()
        return _("by %(name)s") % {"name": name} if name else _("by the tutor")
    profile = getattr(user, "portal_profile", None)
    if profile is None:
        return _("by another account")
    role = _("student account") if profile.role == "student" else _("parent account")
    # Die E-Mail sieht nur der Tutor - im Portal könnten Geschwister mitlesen.
    if viewer == TUTOR and user.email:
        return _("by the %(role)s (%(email)s)") % {"role": role, "email": user.email}
    return _("by the %(role)s") % {"role": role}


def _origin(at, created_via, in_series, booked_by, tutor_id, viewer, portal_user) -> BookingOrigin:
    parts = [
        p
        for p in (
            _channel(created_via, in_series),
            account_phrase(booked_by, tutor_id, viewer, portal_user),
        )
        if p
    ]
    note = ""
    if booked_by is None:
        note = _("The booking account is only recorded since 29 Sep 2026.")
    return BookingOrigin(at=at, how=" ".join(parts), note=note)


def booking_origin(lesson, viewer=TUTOR, portal_user=None) -> BookingOrigin:
    return _origin(
        lesson.created_at,
        lesson.created_via,
        bool(lesson.recurring_session_id),
        lesson.booked_by,
        lesson.contract.user_id,
        viewer,
        portal_user,
    )


def cancellation_info(record, viewer=TUTOR, portal_user=None) -> CancellationInfo:
    """record: CancelledSession."""
    tutor_id = record.contract.user_id
    channel = (
        _("with the whole series via the portal")
        if record.cancelled_via == "portal_series"
        else _("via the portal")
    )
    who = account_phrase(record.cancelled_by, tutor_id, viewer, portal_user)
    booked = None
    if record.booked_at:
        booked = _origin(
            record.booked_at,
            record.created_via,
            record.was_series,
            record.booked_by,
            tutor_id,
            viewer,
            portal_user,
        )
    return CancellationInfo(
        cancelled_at=record.cancelled_at,
        cancelled_how=" ".join(p for p in (channel, who) if p),
        booked=booked,
    )


def cancelled_overview(contract, viewer=TUTOR, portal_user=None, limit=20) -> list[tuple]:
    """Die zuletzt abgesagten Termine eines Vertrags als (CancelledSession, CancellationInfo)."""
    from apps.lessons.cancelled_models import CancelledSession

    records = CancelledSession.objects.filter(contract=contract).select_related(
        "contract",
        "cancelled_by",
        "cancelled_by__portal_profile",
        "booked_by",
        "booked_by__portal_profile",
    )[:limit]
    return [(record, cancellation_info(record, viewer, portal_user)) for record in records]
