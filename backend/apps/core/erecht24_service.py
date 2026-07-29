"""
e-recht24 Rechtstexte API — client registration, push webhook, and pull.

Flow:
  1. Run `manage.py erecht24_register` once to register this app as a client.
  2. e-recht24 calls the push webhook at /erecht24/push/ whenever texts change.
  3. The service also pulls current texts on first cache miss.
"""

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

BASE_URL = "https://api.e-recht24.de/v2"
CACHE_TTL = 60 * 60 * 24  # 24 h
CACHE_KEY_IMPRINT_DE = "erecht24_imprint_de"
CACHE_KEY_IMPRINT_EN = "erecht24_imprint_en"
CACHE_KEY_PRIVACY_DE = "erecht24_privacy_de"
CACHE_KEY_PRIVACY_EN = "erecht24_privacy_en"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _headers() -> dict:
    from django.core.exceptions import ImproperlyConfigured

    api_key = getattr(settings, "ERECHT24_API_KEY", "")
    if not api_key:
        raise ImproperlyConfigured("ERECHT24_API_KEY ist nicht gesetzt.")
    return {
        "eRecht24-api-key": api_key,
        "eRecht24-plugin-key": getattr(settings, "ERECHT24_PLUGIN_KEY", ""),
        "content-type": "application/json",
    }


def _request(method: str, path: str, body: dict | None = None) -> dict | None:
    url = f"{BASE_URL}/{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=_headers(), method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (URLError, Exception) as exc:
        logger.warning("e-recht24 API error [%s %s]: %s", method, path, exc)
        return None


def register_client(push_uri: str) -> dict | None:
    """Register this app as an e-recht24 client. Returns {client_id, secret}."""
    from urllib.parse import urlparse

    parsed = urlparse(push_uri)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise ValueError(f"Ungültige push_uri: {push_uri!r}")
    return _request(
        "POST",
        "clients",
        {
            "push_uri": push_uri,
            "push_method": "POST",
            "cms": "Django",
            "cms_version": "6.0",
            "plugin_name": "Preceptly",
            "author_mail": "info@preceptly.de",
        },
    )


def delete_client(client_id: int) -> dict | None:
    return _request("DELETE", f"clients/{client_id}")


# ---------------------------------------------------------------------------
# Pull legal texts and store in cache
# ---------------------------------------------------------------------------


ALLOWED_TAGS = [
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "a",
    "strong",
    "em",
    "br",
    "span",
    "div",
]


ALLOWED_ATTRS = {"a": ["href", "title", "target"]}


MAX_CONTENT_LENGTH = 100_000


def _sanitize_html(raw: str) -> str:
    if len(raw) > MAX_CONTENT_LENGTH:
        raise ValueError(
            f"HTML-Inhalt überschreitet maximale Länge von {MAX_CONTENT_LENGTH} Zeichen "
            f"(erhalten: {len(raw)} Zeichen)."
        )
    try:
        import nh3

        return nh3.clean(
            raw,
            tags=set(ALLOWED_TAGS),
            attributes={k: set(v) for k, v in ALLOWED_ATTRS.items()},
        )
    except ImportError:
        import html as html_lib

        return html_lib.escape(raw)


def _store(data: dict, key_de: str, key_en: str) -> str:
    html_de = data.get("html_de", "")
    html_en = data.get("html_en", html_de)
    html_de = _sanitize_html(html_de)
    html_en = _sanitize_html(html_en)
    cache.set(key_de, html_de, CACHE_TTL)
    cache.set(key_en, html_en, CACHE_TTL)
    return html_de


def pull_imprint() -> str:
    data = _request("GET", "imprint")
    if data:
        return _store(data, CACHE_KEY_IMPRINT_DE, CACHE_KEY_IMPRINT_EN)
    return ""


def pull_privacy_policy() -> str:
    data = _request("GET", "privacyPolicy")
    if data:
        return _store(data, CACHE_KEY_PRIVACY_DE, CACHE_KEY_PRIVACY_EN)
    return ""


# ---------------------------------------------------------------------------
# Public accessors (used by views)
# ---------------------------------------------------------------------------


def get_imprint(lang: str = "de") -> str:
    key = CACHE_KEY_IMPRINT_DE if lang == "de" else CACHE_KEY_IMPRINT_EN
    cached = cache.get(key)
    if cached:
        return cached
    try:
        pull_imprint()
        return cache.get(key) or ""
    except Exception:
        logger.warning("e-recht24 nicht erreichbar, kein Fallback verfügbar")
        return ""


def get_privacy_policy(lang: str = "de") -> str:
    key = CACHE_KEY_PRIVACY_DE if lang == "de" else CACHE_KEY_PRIVACY_EN
    cached = cache.get(key)
    if cached:
        return cached
    try:
        pull_privacy_policy()
        return cache.get(key) or ""
    except Exception:
        logger.warning("e-recht24 nicht erreichbar, kein Fallback verfügbar")
        return ""


PUSH_TYPE_PING = "ping"
PUSH_TYPE_IMPRINT = "imprint"
PUSH_TYPE_PRIVACY = "privacyPolicy"
VALID_PUSH_TYPES = {PUSH_TYPE_PING, PUSH_TYPE_IMPRINT, PUSH_TYPE_PRIVACY}


def handle_push(payload: dict) -> dict:
    """
    Process an incoming push from e-recht24.
    Returns a response dict to be sent back as JSON.
    """
    import hmac

    secret = payload.get("erecht24_secret", "")
    push_type = payload.get("erecht24_type", "")
    expected_secret = getattr(settings, "ERECHT24_PUSH_SECRET", "")

    if not expected_secret or not hmac.compare_digest(
        str(secret).encode(), expected_secret.encode()
    ):
        logger.warning("e-recht24 push: invalid secret")
        return {"code": 403, "message": "forbidden"}

    if push_type not in VALID_PUSH_TYPES:
        return {"code": 400, "message": "unknown type"}

    if push_type == PUSH_TYPE_PING:
        return {"code": 200, "message": "pong"}

    if push_type == PUSH_TYPE_IMPRINT:
        pull_imprint()
        logger.info("e-recht24 push: imprint updated")
    elif push_type == PUSH_TYPE_PRIVACY:
        pull_privacy_policy()
        logger.info("e-recht24 push: privacy policy updated")

    return {"code": 200, "message": "ok"}
