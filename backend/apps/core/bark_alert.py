"""
Logging-Handler, der bei Fehlern zusaetzlich zur Admin-E-Mail eine kurze,
alarmfreie Bark-Push-Benachrichtigung verschickt.

Enthaelt bewusst nur die genaue Fehlerquelle (Exception-Typ + Datei:Zeile),
keine Request-Daten, keinen Traceback und keine Nutzerdaten - Push-
Benachrichtigungen koennen auf dem Sperrbildschirm sichtbar sein.
"""

import logging
import traceback
import urllib.parse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BarkErrorHandler(logging.Handler):
    """Sendet ERROR-Log-Eintraege als passive (alarmfreie) Bark-Push-Nachricht.

    Laeuft zusaetzlich zur bestehenden AdminEmailHandler-Benachrichtigung,
    nicht als Ersatz. Fehler beim Versand duerfen niemals die eigentliche
    Fehlerbehandlung stoeren.
    """

    def emit(self, record):
        server_url = getattr(settings, "BARK_SERVER_URL", "")
        device_key = getattr(settings, "BARK_DEVICE_KEY", "")
        if not server_url or not device_key:
            return
        try:
            title = "Preceptly Fehler"
            body = self._format_source(record)
            url = (
                f"{server_url.rstrip('/')}/{device_key}/"
                f"{urllib.parse.quote(title, safe='')}/{urllib.parse.quote(body, safe='')}"
            )
            auth_user = getattr(settings, "BARK_AUTH_USER", "")
            auth_password = getattr(settings, "BARK_AUTH_PASSWORD", "")
            requests.get(
                url,
                params={"level": "passive", "group": "preceptly"},
                auth=(auth_user, auth_password) if auth_user else None,
                timeout=5,
            )
        except Exception:
            logger.warning("Bark-Push konnte nicht gesendet werden", exc_info=True)

    @staticmethod
    def _format_source(record):
        """Extrahiert nur die Fundstelle (Datei:Zeile, Exception-Typ) - keine Details."""
        if record.exc_info and record.exc_info[0] is not None:
            exc_type = record.exc_info[0].__name__
            last_frame = None
            for frame in traceback.extract_tb(record.exc_info[2]):
                last_frame = frame
            if last_frame:
                filename = last_frame.filename.split("/backend/")[-1]
                return f"{exc_type} in {filename}:{last_frame.lineno} ({last_frame.name})"
            return exc_type
        return record.getMessage()[:120]
