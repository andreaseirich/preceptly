"""Kalender per Adresse einbinden: Abruf und Auswertung einer iCal-Adresse.

Gedacht für die "geheime Adresse im iCal-Format" von Google Kalender (Einstellungen des Kalenders -> Kalender
integrieren). Mit der Adresse lässt sich der Kalender nur lesen; Preceptly macht daraus Blockzeiten. Anders als der
CalDAV-Abgleich (iCloud) braucht das weder ein Passwort noch OAuth.

Dieses Modul kennt weder Django noch die Datenbank: Es holt eine Adresse ab und gibt die Termine im Zeitraum zurück. Das
Speichern und das Abgleichen mit den Blockzeiten steht in ics_sync.py.

Sicherheit: Der Server ruft eine Adresse ab, die ein Benutzer eingibt (SSRF-Risiko). Deshalb gilt:

- nur https, nur Rechner aus ALLOWED_SOURCES und nur dort erlaubte Pfade, keine Zugangsdaten in der Adresse, nur Port 443;
- vor jedem Abruf und nach jeder Weiterleitung wird neu geprüft, außerdem muss der Name auf eine öffentliche Adresse
  zeigen (nie auf interne, lokale oder reservierte Bereiche);
- Weiterleitungen werden von Hand verfolgt (höchstens 3), Zeitlimits, höchstens 5 MB;
- Fehlermeldungen und Logs enthalten **nie** die Adresse: Sie ist wie ein Passwort.

Bekannte Restlücke: Der Name wird für die Prüfung einmal selbst aufgelöst und beim eigentlichen Abruf von requests ein
zweites Mal (DNS-Rebinding). Das Risiko ist klein, solange nur calendar.google.com erlaubt ist. Wird ALLOWED_SOURCES um
Rechner erweitert, die Dritte kontrollieren können, muss der Abruf an die geprüfte IP gebunden werden.
"""

import ipaddress
import logging
import socket
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
import requests

logger = logging.getLogger(__name__)

# Rechner, von denen abgerufen werden darf, mit dem Pfad, mit dem die Adresse beginnen muss.
# Google: https://calendar.google.com/calendar/ical/<Kalender>/private-<Schlüssel>/basic.ics
ALLOWED_SOURCES = {"calendar.google.com": "/calendar/ical/"}

MAX_URL_LENGTH = 2000
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = (5, 15)  # Verbindung, Lesen (Sekunden)
MAX_REDIRECTS = 3
MAX_EVENTS = 5000  # Einträge (VEVENT) in der Datei
MAX_OCCURRENCES = 3000  # einzelne Termine im Zeitraum, nach dem Auflösen von Wiederholungen
DEFAULT_TIMEZONE = ZoneInfo("Europe/Berlin")
USER_AGENT = "Preceptly-Calendar-Import/1.0"

# Wiederholungen im Sekunden- oder Minutentakt gibt es in echten Kalendern nicht; sie würden nur Rechenzeit fressen.
_TOO_FREQUENT = {"SECONDLY", "MINUTELY"}


class IcsError(Exception):
    """Fehler beim Einbinden. code nennt die Art (für die Meldung an den Benutzer), message ist harmlos und enthält
    nie die Adresse."""

    def __init__(self, code, message=""):
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class Occurrence:
    """Ein einzelner Termin im Zeitraum (bei Wiederholungen jeder einzelne Tag)."""

    key: str  # eindeutig je Termin und Tag: Kennung des Eintrags und Beginn
    uid: str
    summary: str
    start: datetime  # mit Zeitzone
    end: datetime  # mit Zeitzone
    all_day: bool


def normalize_ics_url(raw, allowed_sources=None):
    """Prüft die eingegebene Adresse und gibt sie bereinigt zurück (https, ohne Fragment).

    webcal:// und webcals:// werden zu https://. Löst IcsError aus, wenn die Adresse nicht erlaubt ist."""
    allowed = ALLOWED_SOURCES if allowed_sources is None else allowed_sources
    value = (raw or "").strip()
    if not value:
        raise IcsError("empty", "No address entered.")
    if len(value) > MAX_URL_LENGTH or any(ord(c) < 32 or c.isspace() for c in value):
        raise IcsError("bad_url", "The address is not valid.")
    lowered = value.lower()
    for prefix in ("webcals://", "webcal://"):
        if lowered.startswith(prefix):
            value = "https://" + value[len(prefix) :]
            break
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        raise IcsError("bad_url", "The address is not valid.") from None
    if parts.scheme.lower() != "https" or not host:
        raise IcsError("bad_url", "The address must start with https:// or webcal://.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise IcsError("bad_url", "The address is not valid.")
    if port not in (None, 443):
        raise IcsError("bad_url", "The address is not valid.")
    prefix_path = allowed.get(host)
    if prefix_path is None:
        raise IcsError(
            "host_not_allowed", "Only addresses of supported calendar providers can be used."
        )
    if not parts.path.startswith(prefix_path):
        raise IcsError("host_not_allowed", "This is not the secret iCal address of a calendar.")
    return urlunsplit(("https", host, parts.path, parts.query, ""))


def _public_addresses(host):
    """Adressen, auf die der Name zeigt. Leere Liste, wenn er sich nicht auflösen lässt."""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        return []
    return sorted({info[4][0] for info in infos})


def _ensure_public(host, resolve):
    addresses = resolve(host)
    if not addresses:
        raise IcsError("fetch_failed", "The calendar server could not be found.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%")[0])
        except ValueError:
            raise IcsError("fetch_failed", "The calendar server could not be reached.") from None
        if not ip.is_global or ip.is_multicast:
            raise IcsError("host_not_allowed", "The address points to a non-public server.")


def fetch_ics(url, *, get=None, resolve=None, allowed_sources=None):
    """Holt die Datei und gibt den Inhalt zurück. get und resolve lassen sich in Tests ersetzen."""
    get = get or requests.get
    resolve = resolve or _public_addresses
    current = normalize_ics_url(url, allowed_sources)
    for _hop in range(MAX_REDIRECTS + 1):
        _ensure_public(urlsplit(current).hostname, resolve)
        try:
            response = get(
                current,
                stream=True,
                timeout=TIMEOUT,
                allow_redirects=False,
                headers={"User-Agent": USER_AGENT, "Accept": "text/calendar, */*;q=0.5"},
            )
        except requests.RequestException:
            # Die Ausnahme enthält die Adresse: nicht weitergeben und nicht loggen.
            raise IcsError("fetch_failed", "The calendar server could not be reached.") from None
        try:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location", "")
                current = normalize_ics_url(urljoin(current, location), allowed_sources)
                continue
            if response.status_code != 200:
                raise IcsError(
                    "fetch_failed",
                    f"The calendar server answered with status {response.status_code}.",
                )
            body = bytearray()
            for chunk in response.iter_content(8192):
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise IcsError("too_large", "The calendar file is too large.")
            return bytes(body)
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
    raise IcsError("fetch_failed", "Too many redirects.")


def _as_aware(value, local_tz):
    """Beginn oder Ende als Zeitpunkt mit Zeitzone. Ganztägige Termine gelten von Mitternacht bis Mitternacht Ortszeit,
    Zeiten ohne Zeitzone als Ortszeit."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=local_tz) if value.tzinfo is None else value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=local_tz)
    raise ValueError("unexpected date value")


def parse_occurrences(
    data, window_start, window_end, *, local_tz=DEFAULT_TIMEZONE, max_occurrences=MAX_OCCURRENCES
):
    """Alle Termine im Zeitraum [window_start, window_end), Wiederholungen aufgelöst.

    Übersprungen werden abgesagte Termine und solche, die als "verfügbar" markiert sind (TRANSP:TRANSPARENT, etwa
    Geburtstage und Erinnerungen), sowie Termine ohne Dauer. Löst IcsError aus, wenn die Datei kein Kalender ist
    oder zu viele Termine enthält."""
    try:
        calendar = icalendar.Calendar.from_ical(data)
    except Exception:
        raise IcsError("not_ical", "The file is not a calendar.") from None
    if getattr(calendar, "name", "") != "VCALENDAR":
        raise IcsError("not_ical", "The file is not a calendar.")

    vevents = list(calendar.walk("VEVENT"))
    if len(vevents) > MAX_EVENTS:
        raise IcsError("too_many_events", "The calendar contains too many entries.")
    # Wiederholungen im Sekunden- oder Minutentakt vor dem Auflösen aussortieren
    for event in vevents:
        rule = event.get("RRULE")
        freq = rule.get("FREQ") if rule is not None else None
        if freq and str(freq[0] if isinstance(freq, list) else freq).upper() in _TOO_FREQUENT:
            calendar.subcomponents.remove(event)

    try:
        components = recurring_ical_events.of(calendar).between(window_start, window_end)
    except Exception:
        raise IcsError("not_ical", "The calendar could not be read.") from None

    found = {}
    for component in components:
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            continue
        if str(component.get("TRANSP", "")).upper() == "TRANSPARENT":
            continue
        try:
            raw_start, raw_end = component.start, component.end
            start, end = _as_aware(raw_start, local_tz), _as_aware(raw_end, local_tz)
        except Exception:
            # Weder Titel noch Adresse loggen: beides kann privat sein.
            logger.warning("Skipping a calendar appointment with an unreadable date")
            continue
        if end <= start:
            continue
        all_day = isinstance(raw_start, date) and not isinstance(raw_start, datetime)
        uid = str(component.get("UID", "")).strip()[:250] or f"no-uid-{start.isoformat()}"
        key = f"{uid}|{start.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        summary = " ".join(str(component.get("SUMMARY", "")).split())[:200] or "Termin"
        found[key] = Occurrence(
            key=key, uid=uid, summary=summary, start=start, end=end, all_day=all_day
        )

    occurrences = sorted(found.values(), key=lambda o: (o.start, o.key))
    if len(occurrences) > max_occurrences:
        raise IcsError(
            "too_many_events", "The calendar contains too many appointments in the next months."
        )
    return occurrences


def default_window(now=None, past_days=7, future_days=180):
    """Der Zeitraum, der abgeglichen wird (wie beim CalDAV-Abgleich: 7 Tage zurück, 180 voraus)."""
    now = now or datetime.now(dt_timezone.utc)
    return now - timedelta(days=past_days), now + timedelta(days=future_days)
