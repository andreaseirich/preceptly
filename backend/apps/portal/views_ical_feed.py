"""
Read-only iCal subscribe feed for parent/student portal users - one-way
(Preceptly -> their calendar app), no login required since the feed's UUID
token in the URL is itself the authentication (matches how Google/Apple
calendar subscription URLs work; the token is unguessable and never
displayed anywhere except this user's own portal settings page).
"""

from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.utils import timezone
from icalendar import Calendar, Event

from apps.lessons.models import Session
from apps.portal.models import ParentStudentLink, PortalUser

FEED_WINDOW_PAST_DAYS = 30
FEED_WINDOW_FUTURE_DAYS = 365


def ical_feed(request, token):
    try:
        portal_user = PortalUser.objects.get(ical_feed_token=token)
    except (PortalUser.DoesNotExist, ValidationError, ValueError):
        raise Http404 from None

    contract_ids = ParentStudentLink.objects.filter(parent=portal_user, is_active=True).values_list(
        "contract_id", flat=True
    )

    window_start = timezone.localdate() - timedelta(days=FEED_WINDOW_PAST_DAYS)
    window_end = timezone.localdate() + timedelta(days=FEED_WINDOW_FUTURE_DAYS)
    sessions = (
        Session.objects.filter(
            contract_id__in=contract_ids, date__gte=window_start, date__lte=window_end
        )
        .select_related("contract")
        .order_by("date", "start_time")
    )

    cal = Calendar()
    cal.add("prodid", "-//Preceptly//Portal Calendar Feed//DE")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Preceptly")
    cal.add("method", "PUBLISH")

    for session in sessions:
        start = timezone.make_aware(datetime.combine(session.date, session.start_time))
        end = start + timedelta(minutes=session.duration_minutes)
        event = Event()
        event.add("uid", f"preceptly-portal-session-{session.pk}@preceptly.de")
        event.add(
            "summary", f"Nachhilfe: {session.contract.subjects or session.contract.full_name}"
        )
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("dtstamp", timezone.now())
        if session.notes:
            event.add("description", session.notes)
        cal.add_component(event)

    response = HttpResponse(cal.to_ical(), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="preceptly.ics"'
    return response
