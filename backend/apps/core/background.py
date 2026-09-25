"""Arbeit nach der Antwort im Hintergrund erledigen - vor allem E-Mails.

Der Versand über iCloud-SMTP dauert ein bis mehrere Sekunden. Läuft er in der
Anfrage, wartet der Besucher so lange. Beim Portal-Passwort-Reset verriet die
Wartezeit außerdem, ob es zur Adresse ein Konto gibt: Nur dann geht eine Mail
raus.

run_in_background() startet die Arbeit in einem eigenen Thread, sobald die
laufende Transaktion festgeschrieben ist - wird sie zurückgerollt, geht nichts
raus. Die Sprache der Anfrage wird mitgenommen. Fehler landen im Log. Wer eine
Rückmeldung zum Versand braucht (etwa der Tutor bei einer Portal-Einladung),
ruft den Versand weiter direkt auf.

Mit RUN_IN_BACKGROUND=False (in Tests) läuft alles sofort in der Anfrage, damit
mail.outbox direkt danach stimmt.
"""

import logging
import threading

from django.conf import settings
from django.db import connections, transaction
from django.utils import translation

logger = logging.getLogger(__name__)


def _run(label, language, func, args, kwargs):
    try:
        with translation.override(language):
            func(*args, **kwargs)
    except Exception:
        logger.exception("Hintergrundarbeit fehlgeschlagen: %s", label)


def run_in_background(label, func, *args, **kwargs):
    """func(*args, **kwargs) nach dem Commit in einem eigenen Thread ausführen.

    label erscheint im Thread-Namen und im Log, falls etwas schiefgeht."""
    language = translation.get_language()
    if not getattr(settings, "RUN_IN_BACKGROUND", False):
        _run(label, language, func, args, kwargs)
        return

    def work():
        try:
            _run(label, language, func, args, kwargs)
        finally:
            connections.close_all()  # Verbindungen dieses Threads, sonst bleiben sie offen

    # daemon=False: Ein Neustart wartet, bis die Mail raus ist (höchstens EMAIL_TIMEOUT).
    transaction.on_commit(
        lambda: threading.Thread(target=work, name=f"background: {label}", daemon=False).start()
    )
