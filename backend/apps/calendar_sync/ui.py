"""Was die Einstellungsseite für Kalenderadresse und Kalender-Abo braucht (Meldungen und Daten für die Vorlagen)."""

from django.urls import reverse
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from apps.calendar_sync.models import IcsCalendarSource, TutorCalendarFeed

_ERROR_TEXTS = {
    "empty": _("Please paste the address of your calendar."),
    "bad_url": _("This does not look like a valid calendar address."),
    "host_not_allowed": _("Only the secret iCal address of a Google Calendar can be used here."),
    "fetch_failed": _(
        "The calendar could not be retrieved. Please check the address and try again."
    ),
    "too_large": _("The calendar is too large to import."),
    "not_ical": _("The address does not lead to a calendar."),
    "too_many_events": _("The calendar contains too many appointments to import."),
    "credential": _("Calendar import is not available right now. Please try again later."),
}


def ics_error_message(code):
    """Der Text zu einem Fehlercode. Unbekannte Codes bekommen eine allgemeine Meldung, nie den Rohwert."""
    return _ERROR_TEXTS.get(code, _("The calendar could not be imported."))


def settings_context(request):
    """Daten für die Karten "Kalender per Adresse" und "Kalender-Abo" auf der Einstellungsseite."""
    sources = list(IcsCalendarSource.objects.filter(user=request.user))
    for source in sources:
        source.error_text = (
            ics_error_message(source.last_sync_error) if source.last_sync_error else ""
        )
    feed = TutorCalendarFeed.objects.filter(user=request.user).first()
    context = {
        "ics_sources": sources,
        "ics_source_limit": IcsCalendarSource.MAX_PER_USER,
        "ics_sources_full": len(sources) >= IcsCalendarSource.MAX_PER_USER,
        "tutor_feed": feed,
    }
    if feed:
        url = request.build_absolute_uri(reverse("calendar_sync:tutor_feed", args=[feed.token]))
        context["tutor_feed_url"] = url
        context["tutor_feed_webcal_url"] = "webcal://" + url.split("://", 1)[1]
    return context


def own_note(own):
    """Ein Hinweis für die Meldung nach dem Abgleich. Leer, wenn der Kalender keine eigenen Preceptly-Termine enthält."""
    if not own or not own.get("found"):
        return ""
    text = gettext(
        "{count} appointments come from Preceptly itself and are not imported as blocked times."
    ).format(count=own["found"])
    problems = []
    if own.get("changed"):
        problems.append(
            gettext("{count} have a different time than in Preceptly").format(count=own["changed"])
        )
    if own.get("gone"):
        problems.append(gettext("{count} no longer exist in Preceptly").format(count=own["gone"]))
    if own.get("missing"):
        problems.append(
            gettext("{count} lessons are missing in this calendar").format(count=own["missing"])
        )
    if problems:
        text += " " + gettext("Differences:") + " " + "; ".join(problems) + "."
    return text
