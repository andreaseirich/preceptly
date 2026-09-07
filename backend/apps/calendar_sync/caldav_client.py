"""
Thin wrapper around the `caldav` library: connect, list available calendars,
and CRUD individual events by UID within a specific calendar. Kept separate
from the sync orchestration (sync_service.py) so that logic can be tested
without a real CalDAV server.
"""

from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime as _datetime
from datetime import time as _time
from typing import Optional

import caldav
from caldav.lib.error import NotFoundError
from django.utils import timezone as _timezone


def _normalize_event_dt(value):
    """iCal all-day events carry DTSTART/DTEND as plain dates (no time, no
    tzinfo) rather than datetimes - DTEND is exclusive per RFC 5545 (the
    day *after* the last day). Passed straight through, Django's ORM
    accepts a bare `date` for a DateTimeField but silently treats the
    resulting naive midnight as UTC instead of the local day it actually
    represents (logs a RuntimeWarning and gets it wrong), which is exactly
    what let some blocked times fail to block an adjacent day. Convert
    explicitly to a timezone-aware local midnight instead."""
    if isinstance(value, _datetime):
        return value
    if isinstance(value, _date):
        return _timezone.make_aware(_datetime.combine(value, _time.min))
    return value


class CalDavConnectionError(Exception):
    """Raised when the CalDAV server can't be reached or credentials are
    rejected - distinct from "event not found" style errors below."""

    pass


@dataclass
class ExternalCalendar:
    url: str
    name: str


@dataclass
class ExternalEvent:
    uid: str
    etag: str
    summary: str
    start: "object"  # datetime
    end: "object"  # datetime
    description: str = ""


class CalDavClient:
    """One connection to one tutor's CalDAV account. Does not bind to a
    single calendar - the tutor may push Sessions to one calendar and pull
    BlockedTimes from several others, so every operation below takes an
    explicit calendar_url."""

    def __init__(self, url: str, username: str, password: str):
        try:
            self._client = caldav.DAVClient(url=url, username=username, password=password)
            self._principal = self._client.principal()
        except Exception as e:
            raise CalDavConnectionError(f"Could not connect to CalDAV server: {e}") from e

    def list_event_calendars(self) -> list[ExternalCalendar]:
        """Calendars that support VEVENT - excludes task/reminder lists
        (VTODO-only, e.g. iCloud's default "Reminders" collection): PUTting
        a VEVENT there is rejected by the server (403 Forbidden)."""
        try:
            calendars = self._principal.calendars()
        except Exception as e:
            raise CalDavConnectionError(f"Could not list calendars: {e}") from e

        result = []
        for cal in calendars:
            try:
                supported = cal.get_supported_components()
            except Exception:
                supported = None
            if supported is None or "VEVENT" in supported:
                result.append(ExternalCalendar(url=str(cal.url), name=cal.get_display_name()))
        return result

    def _calendar(self, calendar_url: str) -> caldav.Calendar:
        return caldav.Calendar(client=self._client, url=calendar_url)

    def list_events(self, calendar_url: str, start, end) -> list[ExternalEvent]:
        """All events in [start, end) in the given calendar, regardless of
        whether Preceptly already knows about them."""
        try:
            raw_events = self._calendar(calendar_url).search(
                start=start, end=end, event=True, expand=False
            )
        except Exception as e:
            raise CalDavConnectionError(f"Could not list CalDAV events: {e}") from e

        events = []
        for raw in raw_events:
            vevent = raw.icalendar_component
            uid = str(vevent.get("uid", ""))
            if not uid:
                continue
            dtstart = vevent.get("dtstart")
            dtend = vevent.get("dtend")
            if dtstart is None or dtend is None:
                continue
            events.append(
                ExternalEvent(
                    uid=uid,
                    etag=raw.etag or "",
                    summary=str(vevent.get("summary", "")),
                    description=str(vevent.get("description", "")),
                    start=_normalize_event_dt(dtstart.dt),
                    end=_normalize_event_dt(dtend.dt),
                )
            )
        return events

    def get_event(self, calendar_url: str, uid: str) -> Optional[ExternalEvent]:
        try:
            raw = self._calendar(calendar_url).event_by_uid(uid)
        except NotFoundError:
            return None
        except Exception as e:
            raise CalDavConnectionError(f"Could not fetch CalDAV event {uid}: {e}") from e
        vevent = raw.icalendar_component
        dtstart = vevent.get("dtstart")
        dtend = vevent.get("dtend")
        return ExternalEvent(
            uid=uid,
            etag=raw.etag or "",
            summary=str(vevent.get("summary", "")),
            description=str(vevent.get("description", "")),
            start=_normalize_event_dt(dtstart.dt) if dtstart else None,
            end=_normalize_event_dt(dtend.dt) if dtend else None,
        )

    def create_event(
        self, calendar_url: str, uid: str, summary: str, start, end, description: str = ""
    ) -> str:
        """Returns the new event's etag."""
        try:
            raw = self._calendar(calendar_url).save_event(
                uid=uid, summary=summary, dtstart=start, dtend=end, description=description
            )
        except Exception as e:
            raise CalDavConnectionError(f"Could not create CalDAV event: {e}") from e
        return raw.etag or ""

    def update_event(
        self, calendar_url: str, uid: str, summary: str, start, end, description: str = ""
    ) -> str:
        """Returns the updated event's etag. Creates the event if it no
        longer exists on the server (e.g. deleted directly by the user)."""
        try:
            raw = self._calendar(calendar_url).event_by_uid(uid)
        except NotFoundError:
            return self.create_event(calendar_url, uid, summary, start, end, description)
        except Exception as e:
            raise CalDavConnectionError(f"Could not load CalDAV event {uid}: {e}") from e

        vevent = raw.icalendar_component
        vevent["summary"] = summary
        vevent["dtstart"].dt = start
        vevent["dtend"].dt = end
        if description:
            vevent["description"] = description
        try:
            raw.save()
        except Exception as e:
            raise CalDavConnectionError(f"Could not save CalDAV event {uid}: {e}") from e
        return raw.etag or ""

    def delete_event(self, calendar_url: str, uid: str) -> None:
        try:
            raw = self._calendar(calendar_url).event_by_uid(uid)
        except NotFoundError:
            return
        except Exception as e:
            raise CalDavConnectionError(f"Could not load CalDAV event {uid} for delete: {e}") from e
        try:
            raw.delete()
        except Exception as e:
            raise CalDavConnectionError(f"Could not delete CalDAV event {uid}: {e}") from e
