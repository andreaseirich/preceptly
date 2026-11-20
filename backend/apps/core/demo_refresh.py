"""Die öffentlichen Demo-Konten bleiben aktuell: Ihre Daten werden einmal je Kalendertag neu erzeugt.

Der Seed (`seed_demo_data`) rechnet alle Termine vom heutigen Datum aus. Würde er nur einmal laufen, lägen nach ein bis zwei Monaten alle
Termine in der Vergangenheit und die Demo sähe leer aus (so war es: zuletzt erzeugt am 23.06.2026, keine Stunde ab heute). Statt eines
Zeitplaners prüft diese Middleware bei jedem Zugriff eines Demo-Kontos, ob heute schon aufgefrischt wurde. Wenn nicht, erzeugt sie die
Daten neu. Dasselbe Muster nutzt die Bereinigung der Zugriffsprotokolle (`RequestLogMiddleware._maybe_purge`): eine Sperre im Cache, kein
Cron.

Regeln:
- Nur ein Demo-Konto löst die Auffrischung aus, und nur dort, wo es die Demo-Konten schon gibt. Es wird nie eine Demo angelegt, wo keine
  ist (die Konten haben ein öffentliches Passwort).
- Die Konten und ihre Profile bleiben bestehen (`--refresh`), sonst bräche ein laufender Login ab. Erzeugt und gelöscht wird in einer
  Transaktion: Schlägt etwas fehl, bleibt der alte Stand, und die Demo ist nie halb leer.
- Eine Sperre je Kalendertag (deutsches Datum) verhindert, dass mehrere Zugriffe gleichzeitig auffrischen. Schlägt es fehl, gibt es nach
  10 Minuten einen neuen Versuch, kein Dauerfeuer und keine Sperre bis morgen.
- Änderungen, die Besucher in der Demo vornehmen, sind spätestens am nächsten Tag weg. Das war schon die Absicht (siehe `demo_guard`).
"""

import logging
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from apps.core.demo_guard import is_demo_user

logger = logging.getLogger(__name__)

RUNNING_SECONDS = (
    5 * 60
)  # so lange gilt "läuft gerade", falls der Prozess dabei stirbt (zum Beispiel bei einem Deploy)
DONE_SECONDS = (
    36 * 3600
)  # über den Tag hinaus; der Schlüssel enthält das Datum, ein neuer Tag braucht einen neuen Lauf
RETRY_SECONDS = 10 * 60  # nach einem Fehler: neuer Versuch erst nach dieser Zeit


def _lock_key(day):
    return f"demo_refresh:{day.isoformat()}"


def refresh_demo_data_if_due(user, today=None):
    """Erzeugt die Demo-Daten neu, wenn `user` ein Demo-Konto ist und heute noch nicht aufgefrischt wurde.

    Gibt True zurück, wenn aufgefrischt wurde. Wirft nie: Ein Fehler hier darf den Zugriff des Besuchers nicht verhindern.
    """
    if not is_demo_user(user):
        return False
    today = today or timezone.localdate()
    key = _lock_key(today)
    try:
        if not cache.add(key, "running", RUNNING_SECONDS):
            return False  # heute schon erledigt, oder ein anderer Zugriff ist gerade dabei
    except Exception:  # noqa: BLE001 - ohne Cache lieber nichts tun als bei jedem Zugriff neu erzeugen
        logger.warning("Demo-Auffrischung: Sperre im Cache nicht erreichbar", exc_info=True)
        return False

    try:
        with transaction.atomic():
            call_command("seed_demo_data", "--refresh", stdout=StringIO())
    except Exception:  # noqa: BLE001
        logger.exception(
            "Demo-Daten konnten nicht aufgefrischt werden, neuer Versuch in 10 Minuten"
        )
        cache.set(key, "failed", RETRY_SECONDS)
        return False

    cache.set(key, "done", DONE_SECONDS)
    logger.info("Demo-Daten für den %s neu erzeugt", today.isoformat())
    return True


class DemoFreshnessMiddleware:
    """Frischt die Demo-Daten beim ersten Zugriff eines Demo-Kontos am Tag auf. Alle anderen Zugriffe laufen unberührt durch."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if is_demo_user(user):
            refresh_demo_data_if_due(user)
        return self.get_response(request)
