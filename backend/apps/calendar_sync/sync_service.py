"""
Orchestrates one-way sync between one tutor's Sessions/BlockedTimes and
their connected external CalDAV calendars.

Deliberately one direction per object type (confirmed with the user
2026-09-04, simpler than full two-way and matches how tutors actually
want their calendars organized):

- Sessions are pushed to the tutor's chosen "sessions_target" calendar.
  Never read back - editing/deleting the pushed copy externally does not
  change the Session, it only means Preceptly stops touching that copy
  (mapping is dropped, not recreated) once it notices the copy is gone.
- BlockedTimes are imported *from* every calendar the tutor marked as a
  "blocked_time_source" (there can be several - e.g. separate personal and
  work calendars). Never written to - a BlockedTime created directly in
  Preceptly is not pushed anywhere. If the source event is edited
  externally the imported BlockedTime is updated to match; if it's
  deleted externally the imported BlockedTime is deleted too. Deletion is
  decided once, after listing *every* source calendar this cycle (a
  mapping whose UID isn't in any of them anymore), not per-source - a
  tutor with several source calendars would otherwise have a mapping
  wrongly deleted the moment any one *other* source's listing didn't
  happen to contain its UID.

No conflict detection is needed anymore: since each type only flows one
direction, there is no scenario where both sides of the same object
changed independently. SyncConflict/conflict-resolution UI (from the
earlier two-way design) is left in place but will simply never receive
new entries under this model.
"""

import logging
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.caldav_client import CalDavClient, CalDavConnectionError
from apps.calendar_sync.crypto import decrypt_password
from apps.calendar_sync.models import (
    CalendarConnection,
    ExternalCalendarEventMapping,
    SyncedCalendar,
)
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


def _session_bounds(session: Session):
    from apps.lessons.services import LessonConflictService

    return LessonConflictService.calculate_time_block(session)


def sync_connection(connection: CalendarConnection) -> dict:
    """Runs one full sync cycle for a single connection. Returns a summary
    dict for logging/tests. Never raises for per-object failures - those
    are counted in summary['errors'] and logged, so one bad event doesn't
    abort the whole cycle."""
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

    sessions_target = connection.synced_calendars.filter(
        role=SyncedCalendar.ROLE_SESSIONS_TARGET
    ).first()
    blocked_sources = list(
        connection.synced_calendars.filter(role=SyncedCalendar.ROLE_BLOCKED_TIME_SOURCE)
    )

    if sessions_target:
        _sync_sessions_out(
            client,
            connection,
            sessions_target,
            session_ct,
            tutor,
            window_start,
            window_end,
            summary,
        )

    if blocked_sources:
        _sync_blocked_times_in(
            client,
            connection,
            blocked_sources,
            blocked_ct,
            tutor,
            window_start,
            window_end,
            summary,
        )

    connection.last_synced_at = timezone.now()
    connection.last_sync_error = ""
    connection.last_sync_summary = summary
    connection.save(update_fields=["last_synced_at", "last_sync_error", "last_sync_summary"])
    return summary


def _sync_sessions_out(
    client, connection, target, session_ct, tutor, window_start, window_end, summary
):
    calendar_url = target.external_calendar_url
    sessions = Session.objects.filter(
        contract__user=tutor, date__gte=window_start.date(), date__lte=window_end.date()
    )
    known_ids = set()

    for session in sessions:
        known_ids.add(session.pk)
        uid = _session_uid(session)
        title = (
            f"{session.contract.first_name} {session.contract.last_name}".strip()
            or "Preceptly-Stunde"
        )
        start, end = _session_bounds(session)
        try:
            _push_one(
                client,
                connection,
                calendar_url,
                session_ct,
                session.pk,
                uid,
                title,
                (start, end),
                session.updated_at,
                summary,
            )
        except CalDavConnectionError as e:
            summary["errors"] += 1
            logger.warning("CalDAV push failed for session %s: %s", session.pk, e)

    # Sessions deleted locally since the last sync: their mapping's
    # local_object is now None (GenericForeignKey does not cascade), but
    # the mapping row itself is still there - delete the pushed copy too.
    for mapping in ExternalCalendarEventMapping.objects.filter(
        connection=connection, content_type=session_ct
    ):
        if mapping.object_id in known_ids or mapping.local_object is not None:
            continue
        try:
            client.delete_event(calendar_url, mapping.external_uid)
            summary["deleted"] += 1
        except CalDavConnectionError as e:
            summary["errors"] += 1
            logger.warning("Could not delete external event %s: %s", mapping.external_uid, e)
            continue
        mapping.delete()


def _push_one(
    client,
    connection,
    calendar_url,
    content_type,
    object_id,
    uid,
    title,
    bounds,
    updated_at,
    summary,
):
    start, end = bounds
    mapping = ExternalCalendarEventMapping.objects.filter(
        connection=connection, content_type=content_type, object_id=object_id
    ).first()

    if mapping is None:
        etag = client.create_event(calendar_url, uid, title, start, end)
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

    if updated_at <= mapping.local_synced_at:
        return  # nothing changed locally since the last push

    current_external = client.get_event(calendar_url, uid)
    if current_external is None:
        # Pushed once, then removed on the external side - respect that,
        # do not resurrect it. Drop the mapping so a future edit doesn't
        # keep re-checking a dead UID.
        mapping.delete()
        return

    etag = client.update_event(calendar_url, uid, title, start, end)
    mapping.external_etag = etag
    mapping.local_synced_at = updated_at
    mapping.external_synced_at = timezone.now()
    mapping.save(update_fields=["external_etag", "local_synced_at", "external_synced_at"])
    summary["pushed"] += 1


def _sync_blocked_times_in(
    client, connection, sources, blocked_ct, tutor, window_start, window_end, summary
):
    # Phase 1: gather every source calendar's current listing first, so the
    # deletion check in phase 3 has the full picture before deciding
    # anything is actually gone.
    all_external_by_uid = {}
    for source in sources:
        try:
            events = client.list_events(source.external_calendar_url, window_start, window_end)
        except CalDavConnectionError as e:
            summary["errors"] += 1
            logger.warning(
                "Could not list CalDAV events for %s: %s", source.external_calendar_url, e
            )
            continue
        for ev in events:
            all_external_by_uid[ev.uid] = ev

    mappings = ExternalCalendarEventMapping.objects.filter(
        connection=connection, content_type=blocked_ct
    )
    known_mapping_by_uid = {m.external_uid: m for m in mappings}

    # Phase 2: create new BlockedTimes, update changed ones.
    for uid, ev in all_external_by_uid.items():
        mapping = known_mapping_by_uid.get(uid)
        if mapping is None:
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
                external_uid=uid,
                external_etag=ev.etag,
                local_synced_at=bt.updated_at,
                external_synced_at=timezone.now(),
            )
            summary["imported"] += 1
            continue

        if ev.etag and ev.etag != mapping.external_etag:
            local_obj = mapping.local_object
            if local_obj is not None:
                local_obj.title = ev.summary or local_obj.title
                local_obj.description = ev.description or local_obj.description
                local_obj.start_datetime = ev.start
                local_obj.end_datetime = ev.end
                local_obj.save(
                    update_fields=["title", "description", "start_datetime", "end_datetime"]
                )
                mapping.external_etag = ev.etag
                mapping.external_synced_at = timezone.now()
                mapping.local_synced_at = local_obj.updated_at
                mapping.save(
                    update_fields=["external_etag", "external_synced_at", "local_synced_at"]
                )
                summary["pulled"] += 1

    # Phase 3: a mapping missing from *every* source's combined listing is
    # actually gone - delete the imported BlockedTime too.
    for uid, mapping in known_mapping_by_uid.items():
        if uid in all_external_by_uid:
            continue
        local_obj = mapping.local_object
        if local_obj is not None:
            local_obj.delete()
        mapping.delete()
        summary["deleted"] += 1
