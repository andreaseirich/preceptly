"""
Views for connecting/managing a tutor's external calendar sync.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.caldav_client import CalDavClient, CalDavConnectionError
from apps.calendar_sync.crypto import CalendarCredentialError, decrypt_password, encrypt_password
from apps.calendar_sync.models import CalendarConnection, SyncConflict, SyncedCalendar

# Well-known CalDAV discovery URLs - fixed per provider, so the tutor only
# ever enters their account credentials, never a URL they'd have to look up.
PROVIDER_CALDAV_URLS = {
    CalendarConnection.PROVIDER_ICLOUD: "https://caldav.icloud.com/",
}


@login_required
@require_POST
def connect_calendar(request):
    provider = request.POST.get("provider", "icloud").strip()
    caldav_username = request.POST.get("caldav_username", "").strip()
    caldav_password = request.POST.get("caldav_password", "").strip()

    # Only the (non-sensitive) username is ever echoed back on error - the
    # password is never re-populated, so a failed attempt does not force
    # retyping the Apple ID too.
    error_redirect = (
        reverse("core:settings")
        + "?"
        + urlencode({"calendar_username": caldav_username})
        + "#calendar-sync"
    )

    caldav_url = PROVIDER_CALDAV_URLS.get(provider)
    if not caldav_url:
        messages.error(request, _("Unsupported provider."))
        return redirect(error_redirect)

    if not (caldav_username and caldav_password):
        messages.error(request, _("Please fill in all fields."))
        return redirect(error_redirect)

    try:
        # Fail fast with a clear message instead of silently saving broken
        # credentials that would only surface as an opaque error on the
        # next scheduled sync run.
        CalDavClient(caldav_url, caldav_username, caldav_password)
    except CalDavConnectionError as e:
        messages.error(request, _("Could not connect: {error}").format(error=e))
        return redirect(error_redirect)

    try:
        encrypted = encrypt_password(caldav_password)
    except CalendarCredentialError:
        messages.error(
            request, _("Calendar sync is not available right now. Please try again later.")
        )
        return redirect(error_redirect)

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
    messages.success(request, _("Calendar connected. Now choose which calendars to sync."))
    return redirect(reverse("calendar_sync:configure"))


@login_required
def configure_calendars(request):
    connection = get_object_or_404(CalendarConnection, user=request.user)

    if request.method == "POST":
        sessions_target_url = request.POST.get("sessions_target", "").strip()
        blocked_source_urls = set(request.POST.getlist("blocked_sources"))

        SyncedCalendar.objects.filter(connection=connection).delete()
        rows = []
        if sessions_target_url:
            rows.append(
                SyncedCalendar(
                    connection=connection,
                    external_calendar_url=sessions_target_url,
                    display_name=request.POST.get(f"name_{sessions_target_url}", ""),
                    role=SyncedCalendar.ROLE_SESSIONS_TARGET,
                )
            )
        for url in blocked_source_urls:
            rows.append(
                SyncedCalendar(
                    connection=connection,
                    external_calendar_url=url,
                    display_name=request.POST.get(f"name_{url}", ""),
                    role=SyncedCalendar.ROLE_BLOCKED_TIME_SOURCE,
                )
            )
        SyncedCalendar.objects.bulk_create(rows)
        messages.success(request, _("Calendar selection saved."))
        return redirect(reverse("core:settings") + "#calendar-sync")

    try:
        password = decrypt_password(bytes(connection.encrypted_password))
        client = CalDavClient(connection.caldav_url, connection.caldav_username, password)
        available = client.list_event_calendars()
    except CalDavConnectionError as e:
        messages.error(request, _("Could not load your calendars: {error}").format(error=e))
        return redirect(reverse("core:settings") + "#calendar-sync")

    current_target = (
        connection.synced_calendars.filter(role=SyncedCalendar.ROLE_SESSIONS_TARGET)
        .values_list("external_calendar_url", flat=True)
        .first()
    )
    current_sources = set(
        connection.synced_calendars.filter(
            role=SyncedCalendar.ROLE_BLOCKED_TIME_SOURCE
        ).values_list("external_calendar_url", flat=True)
    )

    return render(
        request,
        "calendar_sync/configure_calendars.html",
        {
            "connection": connection,
            "available_calendars": available,
            "current_target": current_target,
            "current_sources": current_sources,
        },
    )


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
