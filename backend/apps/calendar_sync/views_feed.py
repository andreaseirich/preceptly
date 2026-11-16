"""Kalender-Abo für Tutoren: der öffentliche Abruf (Token statt Login) und das Verwalten des Links in den Einstellungen."""

import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST, require_safe

from apps.calendar_sync.feed import build_feed
from apps.calendar_sync.models import TutorCalendarFeed

FETCHED_UPDATE_EVERY = timedelta(minutes=5)


def _back():
    return redirect(reverse("core:settings") + "?section=calendar-sync")


@require_safe
def tutor_feed(request, token):
    """Öffentlich, ohne Login: Der geheime Token in der Adresse ist die Berechtigung."""
    feed = (
        TutorCalendarFeed.objects.select_related("user", "user__profile")
        .filter(token=token)
        .first()
    )
    if feed is None or not feed.user.is_active:
        raise Http404

    now = timezone.now()
    if feed.last_fetched_at is None or now - feed.last_fetched_at >= FETCHED_UPDATE_EVERY:
        TutorCalendarFeed.objects.filter(pk=feed.pk).update(last_fetched_at=now)

    response = HttpResponse(build_feed(feed, now), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="preceptly.ics"'
    response["Cache-Control"] = "private, max-age=300"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    return response


@login_required
@require_POST
def feed_enable(request):
    TutorCalendarFeed.objects.get_or_create(user=request.user)
    messages.success(request, _("Your calendar subscription link is ready."))
    return _back()


@login_required
@require_POST
def feed_renew(request):
    updated = TutorCalendarFeed.objects.filter(user=request.user).update(
        token=uuid.uuid4(), last_fetched_at=None
    )
    if updated:
        messages.success(request, _("New link created. The old link no longer works."))
    return _back()


@login_required
@require_POST
def feed_disable(request):
    TutorCalendarFeed.objects.filter(user=request.user).delete()
    messages.success(request, _("Calendar subscription switched off. The link no longer works."))
    return _back()


@login_required
@require_POST
def feed_names(request):
    TutorCalendarFeed.objects.filter(user=request.user).update(
        include_student_names=request.POST.get("include_student_names") == "on"
    )
    messages.success(request, _("Saved."))
    return _back()
