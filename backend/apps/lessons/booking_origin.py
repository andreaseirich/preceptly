"""Wann und von wem eine Stunde gebucht wurde - für die Detailseiten.

Seit 29.09.2026 merkt sich jede neue Stunde das buchende Konto
(Session.booked_by) und den Weg (Session.created_via). Ältere Stunden kennen
nur den Zeitpunkt und, bei Einzelbuchungen im Portal, den Weg. Anlass: Ein
Schüler bestritt eine Portal-Buchung, und niemand konnte nachsehen, welches
Konto sie angelegt hatte.
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


def _channel(lesson) -> str:
    if lesson.created_via == "portal_booking":
        return _("via the portal")
    if lesson.created_via == "portal_series":
        return _("as a series via the portal")
    if lesson.recurring_session_id:
        return _("as part of a series")
    return ""


def _account(lesson, viewer, portal_user) -> str:
    user = lesson.booked_by
    if user is None:
        return ""
    if viewer == PORTAL and portal_user is not None and user.pk == portal_user.user_id:
        return _("by you")
    if user.pk == lesson.contract.user_id:
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


def booking_origin(lesson, viewer=TUTOR, portal_user=None) -> BookingOrigin:
    """viewer: TUTOR oder PORTAL; portal_user: das angemeldete Portal-Konto."""
    parts = [p for p in (_channel(lesson), _account(lesson, viewer, portal_user)) if p]
    note = ""
    if lesson.booked_by_id is None:
        note = _("The booking account is only recorded since 29 Sep 2026.")
    return BookingOrigin(at=lesson.created_at, how=" ".join(parts), note=note)
