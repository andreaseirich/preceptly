"""
Thin wrapper around the `caldav` library: connect, discover the calendar to
sync with, and CRUD individual events by UID. Kept separate from the sync
orchestration (sync_service.py) so that logic can be tested without a real
CalDAV server.
"""

from dataclasses import dataclass
from typing import Optional

import caldav
from caldav.lib.error import NotFoundError


class CalDavConnectionError(Exception):
    """Raised when the CalDAV server can't be reached or credentials are
    rejected - distinct from "event not found" style errors below."""

    pass


@dataclass
class ExternalEvent:
    uid: str
    etag: str
    summary: str
    start: "object"  # datetime
    end: "object"  # datetime
    description: str = ""


class CalDavClient:
    """One connection to one tutor's CalDAV account, scoped to a single
    calendar (the first one found under the account's principal - good
    enough for a first version; calendar selection can be added later)."""

    def __init__(self, url: str, username: str, password: str):
        try:
            self._client = caldav.DAVClient(url=url, username=username, password=password)
            principal = self._client.principal()
            calendars = principal.calendars()
        except Exception as e:
            raise CalDavConnectionError(f"Could not connect to CalDAV server: {e}") from e
        if not calendars:
            raise CalDavConnectionError("No calendars found for this CalDAV account.")
        self._calendar = calendars[0]

    def list_events(self, start, end) -> list[ExternalEvent]:
        """All events in [start, end), regardless of whether Preceptly
        already knows about them."""
        try:
            raw_events = self._calendar.search(start=start, end=end, event=True, expand=False)
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
                    start=dtstart.dt,
                    end=dtend.dt,
                )
            )
        return events

    def get_event(self, uid: str) -> Optional[ExternalEvent]:
        try:
            raw = self._calendar.event_by_uid(uid)
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
            start=dtstart.dt if dtstart else None,
            end=dtend.dt if dtend else None,
        )

    def create_event(self, uid: str, summary: str, start, end, description: str = "") -> str:
        """Returns the new event's etag."""
        try:
            raw = self._calendar.save_event(
                uid=uid, summary=summary, dtstart=start, dtend=end, description=description
            )
        except Exception as e:
            raise CalDavConnectionError(f"Could not create CalDAV event: {e}") from e
        return raw.etag or ""

    def update_event(self, uid: str, summary: str, start, end, description: str = "") -> str:
        """Returns the updated event's etag. Creates the event if it no
        longer exists on the server (e.g. deleted directly by the user)."""
        try:
            raw = self._calendar.event_by_uid(uid)
        except NotFoundError:
            return self.create_event(uid, summary, start, end, description)
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

    def delete_event(self, uid: str) -> None:
        try:
            raw = self._calendar.event_by_uid(uid)
        except NotFoundError:
            return
        except Exception as e:
            raise CalDavConnectionError(f"Could not load CalDAV event {uid} for delete: {e}") from e
        try:
            raw.delete()
        except Exception as e:
            raise CalDavConnectionError(f"Could not delete CalDAV event {uid}: {e}") from e
