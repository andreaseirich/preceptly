"""
Views for connecting/managing a tutor's external calendar sync.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.caldav_client import CalDavClient, CalDavConnectionError
from apps.calendar_sync.crypto import CalendarCredentialError, encrypt_password
from apps.calendar_sync.models import CalendarConnection, SyncConflict


@login_required
@require_POST
def connect_calendar(request):
    provider = request.POST.get("provider", "icloud").strip()
    caldav_url = request.POST.get("caldav_url", "").strip()
    caldav_username = request.POST.get("caldav_username", "").strip()
    caldav_password = request.POST.get("caldav_password", "").strip()

    if not (caldav_url and caldav_username and caldav_password):
        messages.error(request, _("Please fill in all fields."))
        return redirect(reverse("core:settings") + "#calendar-sync")

    try:
        # Fail fast with a clear message instead of silently saving broken
        # credentials that would only surface as an opaque error on the
        # next scheduled sync run.
        CalDavClient(caldav_url, caldav_username, caldav_password)
    except CalDavConnectionError as e:
        messages.error(request, _("Could not connect: {error}").format(error=e))
        return redirect(reverse("core:settings") + "#calendar-sync")

    try:
        encrypted = encrypt_password(caldav_password)
    except CalendarCredentialError:
        messages.error(
            request, _("Calendar sync is not available right now. Please try again later.")
        )
        return redirect(reverse("core:settings") + "#calendar-sync")

    CalendarConnection.objects.update_or_create(
        user=request.user,
        defaults={
            "provider": provider,
            "caldav_url": caldav_url,
            "caldav_username": caldav_username,
            "encrypted_password": encrypted,
            "sync_enabled": True,
            "last_sync_error": "",
        },
    )
    messages.success(request, _("Calendar connected. The first sync runs within a few minutes."))
    return redirect(reverse("core:settings") + "#calendar-sync")


@login_required
@require_POST
def disconnect_calendar(request):
    CalendarConnection.objects.filter(user=request.user).delete()
    messages.success(request, _("Calendar disconnected."))
    return redirect(reverse("core:settings") + "#calendar-sync")


@login_required
@require_POST
def toggle_calendar_sync(request):
    connection = get_object_or_404(CalendarConnection, user=request.user)
    connection.sync_enabled = not connection.sync_enabled
    connection.save(update_fields=["sync_enabled"])
    return redirect(reverse("core:settings") + "#calendar-sync")


@login_required
def conflict_list(request):
    connection = CalendarConnection.objects.filter(user=request.user).first()
    conflicts = (
        SyncConflict.objects.filter(connection=connection, resolved_at__isnull=True)
        if connection
        else SyncConflict.objects.none()
    )
    return render(request, "calendar_sync/conflicts.html", {"conflicts": conflicts})


@login_required
@require_POST
def resolve_conflict(request, pk):
    conflict = get_object_or_404(SyncConflict, pk=pk, connection__user=request.user)
    resolution = request.POST.get("resolution")
    if resolution not in (SyncConflict.RESOLUTION_LOCAL, SyncConflict.RESOLUTION_EXTERNAL):
        messages.error(request, _("Invalid choice."))
        return redirect("calendar_sync:conflicts")

    if resolution == SyncConflict.RESOLUTION_EXTERNAL:
        # Apply the external snapshot to the local object now; the next
        # sync cycle then pushes/pulls as appropriate since local_synced_at
        # is reset to "before" the local change.
        mapping = conflict.mapping
        local_obj = mapping.local_object
        if local_obj is not None and isinstance(local_obj, BlockedTime):
            ext = conflict.external_snapshot
            local_obj.title = ext.get("title") or local_obj.title
            local_obj.save(update_fields=["title"])
        mapping.local_synced_at = timezone.now()
        mapping.save(update_fields=["local_synced_at"])
    else:
        # Keep the Preceptly version: bump the synced snapshot forward so
        # the next cycle just re-pushes the current local state.
        mapping = conflict.mapping
        mapping.local_synced_at = timezone.now()
        mapping.save(update_fields=["local_synced_at"])

    conflict.resolution = resolution
    conflict.resolved_at = timezone.now()
    conflict.save(update_fields=["resolution", "resolved_at"])
    messages.success(request, _("Conflict resolved."))
    return redirect("calendar_sync:conflicts")
