"""
Orchestrates two-way sync between one tutor's Sessions/BlockedTimes and
their connected external CalDAV calendar.

Direction of truth per object:
- Local object deleted -> delete the external event and the mapping
  (explicit tutor action, safe to mirror).
- External event for a BlockedTime deleted -> delete the local BlockedTime
  and the mapping (mirrors real life: the external appointment is gone).
- External event for a Session deleted -> only drop the mapping. A Session
  is a paid teaching record; it must never be deleted just because a
  calendar event disappeared.
- Both sides changed since the last successful sync -> SyncConflict,
  skipped until the tutor resolves it manually.
- New external event with no mapping -> imported as a new BlockedTime
  (Preceptly can't know it was a teaching session, only that the tutor is
  busy then).
"""

import logging
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.caldav_client import CalDavClient, CalDavConnectionError, ExternalEvent
from apps.calendar_sync.crypto import decrypt_password
from apps.calendar_sync.models import CalendarConnection, ExternalCalendarEventMapping, SyncConflict
from apps.lessons.models import Session

logger = logging.getLogger(__name__)

SYNC_WINDOW_PAST_DAYS = 7
SYNC_WINDOW_FUTURE_DAYS = 180


class SyncError(Exception):
    pass


def _sync_window():
    now = timezone.now()
    return now - timedelta(days=SYNC_WINDOW_PAST_DAYS), now + timedelta(
        days=SYNC_WINDOW_FUTURE_DAYS
    )


def _session_uid(session: Session) -> str:
    return f"preceptly-session-{session.pk}@preceptly.de"


def _blocked_time_uid(blocked_time: BlockedTime) -> str:
    return f"preceptly-blockedtime-{blocked_time.pk}@preceptly.de"


def _session_bounds(session: Session):
    from apps.lessons.services import LessonConflictService

    return LessonConflictService.calculate_time_block(session)


def sync_connection(connection: CalendarConnection) -> dict:
    """Runs one full sync cycle for a single connection. Returns a summary
    dict for logging/tests. Never raises for per-object failures - those
    are recorded on the connection (last_sync_error) and logged, so one
    bad event doesn't abort the whole cycle."""
    summary = {"pushed": 0, "pulled": 0, "imported": 0, "conflicts": 0, "deleted": 0, "errors": 0}

    if not connection.sync_enabled:
        return summary

    try:
        password = decrypt_password(bytes(connection.encrypted_password))
        client = CalDavClient(connection.caldav_url, connection.caldav_username, password)
    except Exception as e:
        connection.last_sync_error = str(e)
        connection.save(update_fields=["last_sync_error"])
        logger.warning("CalDAV connect failed for connection %s: %s", connection.pk, e)
        summary["errors"] += 1
        return summary

    window_start, window_end = _sync_window()
    tutor = connection.user

    session_ct = ContentType.objects.get_for_model(Session)
    blocked_ct = ContentType.objects.get_for_model(BlockedTime)

    known_uids = set()

    # --- Local -> external: Sessions ---------------------------------
    sessions = Session.objects.filter(
        contract__user=tutor, date__gte=window_start.date(), date__lte=window_end.date()
    )
    for session in sessions:
        uid = _session_uid(session)
        known_uids.add(uid)
        try:
            _sync_local_object(
                client,
                connection,
                session_ct,
                session.pk,
                uid,
                title=f"{session.contract.first_name} {session.contract.last_name}".strip()
                or "Preceptly-Stunde",
                bounds=_session_bounds(session),
                updated_at=session.updated_at,
                summary=summary,
            )
        except CalDavConnectionError as e:
            summary["errors"] += 1
            logger.warning("CalDAV sync failed for session %s: %s", session.pk, e)

    # --- Local -> external: BlockedTimes ------------------------------
    blocked_times = BlockedTime.objects.filter(
        user=tutor, start_datetime__lt=window_end, end_datetime__gt=window_start
    )
    for bt in blocked_times:
        uid = _blocked_time_uid(bt)
        known_uids.add(uid)
        try:
            _sync_local_object(
                client,
                connection,
                blocked_ct,
                bt.pk,
                uid,
                title=bt.title,
                bounds=(bt.start_datetime, bt.end_datetime),
                updated_at=bt.updated_at,
                summary=summary,
            )
        except CalDavConnectionError as e:
            summary["errors"] += 1
            logger.warning("CalDAV sync failed for blocked time %s: %s", bt.pk, e)

    # --- Local deletions: mappings whose local object no longer exists --
    for mapping in ExternalCalendarEventMapping.objects.filter(connection=connection):
        if mapping.external_uid in known_uids:
            continue
        # local_object is None if the referenced Session/BlockedTime was
        # deleted (GenericForeignKey doesn't cascade-delete the mapping).
        if mapping.local_object is not None:
            continue
        try:
            client.delete_event(mapping.external_uid)
            summary["deleted"] += 1
        except CalDavConnectionError as e:
            summary["errors"] += 1
            logger.warning("Could not delete external event %s: %s", mapping.external_uid, e)
            continue
        mapping.delete()

    # --- External -> local: new events Preceptly doesn't know about -----
    try:
        external_events = client.list_events(window_start, window_end)
    except CalDavConnectionError as e:
        summary["errors"] += 1
        logger.warning("Could not list CalDAV events for connection %s: %s", connection.pk, e)
        external_events = []

    mapped_uids = set(
        ExternalCalendarEventMapping.objects.filter(connection=connection).values_list(
            "external_uid", flat=True
        )
    )
    for ev in external_events:
        if ev.uid in mapped_uids or ev.uid in known_uids:
            continue
        _import_external_event(connection, blocked_ct, tutor, ev)
        summary["imported"] += 1

    connection.last_synced_at = timezone.now()
    connection.last_sync_error = ""
    connection.last_sync_summary = summary
    connection.save(update_fields=["last_synced_at", "last_sync_error", "last_sync_summary"])
    return summary


def _sync_local_object(
    client, connection, content_type, object_id, uid, title, bounds, updated_at, summary
):
    start, end = bounds
    mapping = ExternalCalendarEventMapping.objects.filter(
        connection=connection, content_type=content_type, object_id=object_id
    ).first()

    if mapping is None:
        etag = client.create_event(uid, title, start, end)
        ExternalCalendarEventMapping.objects.create(
            connection=connection,
            content_type=content_type,
            object_id=object_id,
            external_uid=uid,
            external_etag=etag,
            local_synced_at=updated_at,
            external_synced_at=timezone.now(),
        )
        summary["pushed"] += 1
        return

    current_external = client.get_event(uid)

    if current_external is None:
        # The event no longer exists on the CalDAV server - handled here,
        # driven by this specific UID's lookup, rather than by diffing
        # against a separate list_events() call (which would also flag
        # mappings created earlier this very cycle that have not round-
        # tripped through the server's listing yet).
        if content_type.model_class() is Session:
            # Never delete a Session because its calendar copy vanished -
            # just stop tracking it; the tutor manages sessions in Preceptly.
            mapping.delete()
        else:
            local_obj = mapping.local_object
            if local_obj is not None:
                local_obj.delete()
            mapping.delete()
        summary["deleted"] += 1
        return

    external_etag_now = current_external.etag
    local_changed = updated_at > mapping.local_synced_at
    external_changed = bool(external_etag_now) and external_etag_now != mapping.external_etag

    if local_changed and external_changed:
        SyncConflict.objects.create(
            connection=connection,
            mapping=mapping,
            local_snapshot={"title": title, "start": str(start), "end": str(end)},
            external_snapshot={
                "title": current_external.summary,
                "start": str(current_external.start),
                "end": str(current_external.end),
            },
        )
        summary["conflicts"] += 1
        return

    if local_changed:
        etag = client.update_event(uid, title, start, end)
        mapping.external_etag = etag
        mapping.local_synced_at = updated_at
        mapping.external_synced_at = timezone.now()
        mapping.save(update_fields=["external_etag", "local_synced_at", "external_synced_at"])
        summary["pushed"] += 1
        return

    if external_changed:
        _apply_external_change_to_local(content_type, object_id, current_external)
        mapping.external_etag = current_external.etag
        mapping.external_synced_at = timezone.now()
        # Re-read: applying the change touched updated_at via auto_now.
        mapping.local_synced_at = _current_updated_at(content_type, object_id)
        mapping.save(update_fields=["external_etag", "external_synced_at", "local_synced_at"])
        summary["pulled"] += 1


def _current_updated_at(content_type, object_id):
    model = content_type.model_class()
    return model.objects.get(pk=object_id).updated_at


def _apply_external_change_to_local(content_type, object_id, ev: ExternalEvent):
    model = content_type.model_class()
    obj = model.objects.filter(pk=object_id).first()
    if obj is None:
        return
    if model is BlockedTime:
        obj.title = ev.summary or obj.title
        obj.start_datetime = ev.start
        obj.end_datetime = ev.end
        obj.save(update_fields=["title", "start_datetime", "end_datetime"])
    # Sessions are intentionally not overwritten from external changes -
    # only the title/time on the CalDAV side would change, and silently
    # rewriting a billed lesson's date/time from an external calendar edit
    # is exactly the kind of surprise this sync must not cause. The tutor
    # edits sessions in Preceptly; the external copy is push-only for them.


def _import_external_event(connection, blocked_ct, tutor, ev: ExternalEvent):
    bt = BlockedTime.objects.create(
        user=tutor,
        title=ev.summary or "Importiert aus externem Kalender",
        description=ev.description or "",
        start_datetime=ev.start,
        end_datetime=ev.end,
    )
    ExternalCalendarEventMapping.objects.create(
        connection=connection,
        content_type=blocked_ct,
        object_id=bt.pk,
        external_uid=ev.uid,
        external_etag=ev.etag,
        local_synced_at=bt.updated_at,
        external_synced_at=timezone.now(),
    )


def sync_all_active_connections() -> dict:
    totals = {"pushed": 0, "pulled": 0, "imported": 0, "conflicts": 0, "deleted": 0, "errors": 0}
    for connection in CalendarConnection.objects.filter(sync_enabled=True):
        result = sync_connection(connection)
        for key in totals:
            totals[key] += result.get(key, 0)
    return totals
