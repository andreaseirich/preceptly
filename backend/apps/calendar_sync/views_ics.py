"""Kalender per Adresse einbinden: hinzufügen, abgleichen, pausieren, entfernen (Einstellungen des Tutors).

Die Adresse ist wie ein Passwort: Sie wird nie in einer Meldung, einer Weiterleitung oder einem Formular
zurückgegeben und nie geloggt.
"""

from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.crypto import CalendarCredentialError, encrypt_password
from apps.calendar_sync.ics_import import IcsError, fetch_ics, normalize_ics_url
from apps.calendar_sync.ics_sync import MANUAL_COOLDOWN, sync_source
from apps.calendar_sync.models import IcsCalendarSource
from apps.calendar_sync.ui import ics_error_message, own_note

DEFAULT_NAME = "Google Calendar"


def _back():
    return redirect(reverse("core:settings") + "?section=calendar-sync")


def _report_sync(request, result):
    """Meldet das Ergebnis eines Abgleichs: die Zahlen oder den Fehler, dazu den Hinweis zu den eigenen Terminen."""
    if result.get("error"):
        messages.error(request, ics_error_message(result["error"]))
        return
    messages.success(
        request,
        _("Synced: {created} new, {updated} changed, {deleted} removed.").format(
            created=result["created"], updated=result["updated"], deleted=result["deleted"]
        ),
    )
    note = own_note(result.get("own"))
    if note:
        messages.info(request, note)


@login_required
@require_POST
@ratelimit(key="user", rate="10/h", method="POST", block=True)
def ics_add(request):
    if (
        IcsCalendarSource.objects.filter(user=request.user).count()
        >= IcsCalendarSource.MAX_PER_USER
    ):
        messages.error(
            request,
            _("You can connect up to {count} calendar addresses. Remove one first.").format(
                count=IcsCalendarSource.MAX_PER_USER
            ),
        )
        return _back()

    name = (request.POST.get("name") or "").strip()[:100] or DEFAULT_NAME
    try:
        url = normalize_ics_url(request.POST.get("ics_url", ""))
        url_hash = IcsCalendarSource.hash_url(url)
        if IcsCalendarSource.objects.filter(user=request.user, url_hash=url_hash).exists():
            messages.info(request, _("This calendar is already connected."))
            return _back()
        data = fetch_ics(url)
        encrypted = encrypt_password(url)
    except IcsError as error:
        messages.error(request, ics_error_message(error.code))
        return _back()
    except CalendarCredentialError:
        messages.error(request, ics_error_message("credential"))
        return _back()

    source = IcsCalendarSource.objects.create(
        user=request.user,
        name=name,
        encrypted_url=encrypted,
        url_hash=url_hash,
        host=(urlsplit(url).hostname or "")[:100],
    )
    result = sync_source(source, data=data)
    if result.get("error"):
        # Nichts speichern, was sich nicht lesen lässt: Sonst scheitert es nur still beim nächsten Abgleich.
        source.delete()
        messages.error(request, ics_error_message(result["error"]))
        return _back()

    messages.success(
        request,
        _("Calendar connected. {count} appointments were imported as blocked times.").format(
            count=result["created"]
        ),
    )
    note = own_note(result.get("own"))
    if note:
        messages.info(request, note)
    return _back()


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def ics_sync_now(request, pk):
    source = get_object_or_404(IcsCalendarSource, pk=pk, user=request.user)
    now = timezone.now()
    if source.last_attempt_at and now - source.last_attempt_at < MANUAL_COOLDOWN:
        messages.info(request, _("Please wait a minute before syncing again."))
        return _back()
    _report_sync(request, sync_source(source, now=now))
    return _back()


@login_required
@require_POST
@ratelimit(key="user", rate="30/h", method="POST", block=True)
def ics_all_day(request, pk):
    """Einstellung je Quelle: ganztägige Termine auch blockieren, wenn sie als "Verfügbar" markiert sind. Gilt sofort."""
    source = get_object_or_404(IcsCalendarSource, pk=pk, user=request.user)
    source.block_free_all_day = request.POST.get("block_free_all_day") == "on"
    source.save(update_fields=["block_free_all_day"])
    messages.success(request, _("Saved."))
    _report_sync(request, sync_source(source))
    return _back()


@login_required
@require_POST
def ics_toggle(request, pk):
    source = get_object_or_404(IcsCalendarSource, pk=pk, user=request.user)
    source.sync_enabled = not source.sync_enabled
    source.save(update_fields=["sync_enabled"])
    return _back()


@login_required
@require_POST
def ics_remove(request, pk):
    source = get_object_or_404(IcsCalendarSource, pk=pk, user=request.user)
    # Importierte Blockzeiten gehören zu dieser Quelle und verschwinden mit ihr; sonst blieben unlöschbare Altlasten.
    BlockedTime.objects.filter(ics_mapping__source=source).delete()
    source.delete()
    messages.success(request, _("Calendar removed, along with the blocked times imported from it."))
    return _back()
