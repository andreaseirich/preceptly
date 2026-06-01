"""
e-recht24 Rechtstexte API — fetches imprint and privacy policy HTML.
Results are cached for 24 hours; on error the last known HTML is returned.
"""

import logging
from urllib.request import Request, urlopen
from urllib.error import URLError
import json

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

BASE_URL = "https://api.e-recht24.de/v2"
CACHE_TTL = 60 * 60 * 24  # 24 hours
CACHE_KEY_IMPRINT_DE = "erecht24_imprint_de"
CACHE_KEY_IMPRINT_EN = "erecht24_imprint_en"
CACHE_KEY_PRIVACY_DE = "erecht24_privacy_de"
CACHE_KEY_PRIVACY_EN = "erecht24_privacy_en"


def _fetch(path: str) -> dict | None:
    api_key = getattr(settings, "ERECHT24_API_KEY", "")
    plugin_key = getattr(settings, "ERECHT24_PLUGIN_KEY", "")
    if not api_key or not plugin_key:
        return None
    url = f"{BASE_URL}/{path}"
    req = Request(
        url,
        headers={
            "eRecht24-api-key": api_key,
            "eRecht24-plugin-key": plugin_key,
            "content-type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (URLError, Exception) as exc:
        logger.warning("e-recht24 API error (%s): %s", path, exc)
        return None


def get_imprint(lang: str = "de") -> str:
    cache_key = CACHE_KEY_IMPRINT_DE if lang == "de" else CACHE_KEY_IMPRINT_EN
    cached = cache.get(cache_key)
    if cached:
        return cached
    data = _fetch("imprint")
    if data:
        html_de = data.get("html_de", "")
        html_en = data.get("html_en", html_de)
        cache.set(CACHE_KEY_IMPRINT_DE, html_de, CACHE_TTL)
        cache.set(CACHE_KEY_IMPRINT_EN, html_en, CACHE_TTL)
        return html_de if lang == "de" else html_en
    return cache.get(cache_key) or ""


def get_privacy_policy(lang: str = "de") -> str:
    cache_key = CACHE_KEY_PRIVACY_DE if lang == "de" else CACHE_KEY_PRIVACY_EN
    cached = cache.get(cache_key)
    if cached:
        return cached
    data = _fetch("privacyPolicy")
    if data:
        html_de = data.get("html_de", "")
        html_en = data.get("html_en", html_de)
        cache.set(CACHE_KEY_PRIVACY_DE, html_de, CACHE_TTL)
        cache.set(CACHE_KEY_PRIVACY_EN, html_en, CACHE_TTL)
        return html_de if lang == "de" else html_en
    return cache.get(cache_key) or ""
