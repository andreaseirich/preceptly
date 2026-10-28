"""Abgelaufene Login-Sitzungen löschen (Tabelle django_session).

Gemeint sind die Sitzungen, mit denen Django Anmeldungen und kleine Komfort-Zustände merkt: Portal-Anmeldung, zuletzt
gesehene Kalenderansicht, Empfehlungscode bei der Registrierung. Nicht zu verwechseln mit den Stunden
(apps.lessons.models.Session), an denen Rechnungen und Steuern hängen: Die bleiben unberührt.

Gelöscht wird nur, was abgelaufen ist, also genau das, was Djangos eigener Befehl "clearsessions" tut:

- Eine abgelaufene Sitzung gilt für Django ohnehin als nicht vorhanden. Wer sie hatte, muss sich neu anmelden, mit oder
  ohne die Zeile in der Datenbank.
- Gültige Sitzungen bleiben, niemand wird abgemeldet.
- Kein Modell und keine Datenbank-Beziehung verweist auf die Tabelle. Das Zugriffsprotokoll (RequestLog) speichert nur
  einen Hash des Sitzungsschlüssels, keinen Verweis.

Aufgerufen wird die Funktion einmal am Tag aus der Middleware, zusammen mit dem Aufräumen des Zugriffsprotokolls
(apps/core/middleware.py). Es gibt keinen Zeitplaner.
"""

from django.contrib.sessions.models import Session as LoginSession
from django.utils import timezone


def purge_expired_sessions() -> int:
    """Löscht alle abgelaufenen Login-Sitzungen und gibt die Zahl der gelöschten Zeilen zurück."""
    deleted, _ = LoginSession.objects.filter(expire_date__lt=timezone.now()).delete()
    return deleted
