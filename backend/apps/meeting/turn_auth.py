"""Kurzlebige TURN-Zugangsdaten (TURN REST API).

Ein festes TURN-Passwort steht im Quelltext jeder Meeting-Seite und bleibt
unbegrenzt gültig — wer es einmal abliest, kann den Relay-Server dauerhaft
mitbenutzen. Ist auf dem TURN-Server ``use-auth-secret`` aktiv, erzeugt der
Server stattdessen für jede Meeting-Seite Zugangsdaten, die nach wenigen
Stunden verfallen:

    Benutzername = "<Ablaufzeitpunkt>:<Zufallskennung>"
    Passwort     = base64(HMAC-SHA1(Benutzername, gemeinsames Geheimnis))

Ohne gesetztes Geheimnis bleibt es beim statischen Benutzer, damit ein
Wechsel in beide Richtungen ohne Ausfall möglich ist.
"""

import base64
import hashlib
import hmac
import secrets
import time

from django.conf import settings

DEFAULT_TTL_SECONDS = 8 * 60 * 60


def ephemeral_credential(secret: str, ttl_seconds: int, now: float | None = None):
    """Gibt (Benutzername, Passwort) für ``ttl_seconds`` ab jetzt zurück."""
    expires_at = int((time.time() if now is None else now)) + int(ttl_seconds)
    username = f"{expires_at}:{secrets.token_hex(4)}"
    digest = hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    return username, base64.b64encode(digest).decode()


def ice_servers():
    """ICE-Server-Liste für genau eine Meeting-Seite."""
    servers = [{"urls": url} for url in getattr(settings, "MEETING_STUN_URLS", [])]

    secret = getattr(settings, "TURN_STATIC_AUTH_SECRET", "")
    if secret:
        username, credential = ephemeral_credential(
            secret,
            getattr(settings, "TURN_CREDENTIAL_TTL_SECONDS", DEFAULT_TTL_SECONDS),
        )
    else:
        username = getattr(settings, "TURN_USER", "")
        credential = getattr(settings, "TURN_CREDENTIAL", "")

    for url in getattr(settings, "MEETING_TURN_URLS", []):
        servers.append({"urls": url, "username": username, "credential": credential})
    return servers
