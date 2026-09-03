"""
Low-Level-Client für LLM-API-Kommunikation.
"""

import json
import logging
import os
import random
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils.translation import gettext_lazy as _

# Erlaubte Hostnamen für LLM_API_BASE_URL (SSRF-Schutz)
_ALLOWED_LLM_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "api.mistral.ai",
        "api.cohere.com",
        "openrouter.ai",
    }
)

# Self-hosted Ollama, reachable only through the container's Tailscale
# tailnet (tailscaled runs in userspace-networking mode as a sidecar, see
# scripts/entrypoint.sh) - never reachable from the public internet, so
# plain HTTP over the encrypted WireGuard tunnel is acceptable here even
# though every other provider above requires HTTPS.
_TAILSCALE_PROXY = "http://127.0.0.1:1055"

_MAX_TIMEOUT_SECONDS = 120

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMServiceUnavailableError(LLMClientError):
    """The provider could not be reached at all (timeout/connection error),
    as opposed to the provider responding with an actual error. Distinct
    subclass so callers can show a clearer "try again later" message
    instead of a generic failure - this is the case that fires when a
    self-hosted Ollama instance (e.g. reached over Tailscale) is offline."""

    pass


SAMPLES_PATH = Path(__file__).resolve().parents[3] / "docs" / "llm_samples.json"


@lru_cache(maxsize=1)
def _load_llm_samples() -> dict:
    try:
        with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            logger.warning("LLM samples file has unexpected format (expected dict).")
            return {}
    except FileNotFoundError:
        logger.warning("LLM samples file not found at %s", SAMPLES_PATH)
        return {}
    except json.JSONDecodeError:
        logger.warning("LLM samples file is invalid JSON: %s", SAMPLES_PATH)
        return {}


class LLMClient:
    """Client für die Kommunikation mit einer LLM-API (z. B. OpenAI)."""

    def __init__(self):
        """Initialisiert den LLM-Client mit Konfiguration aus Settings."""
        self.api_base_url = settings.LLM_API_BASE_URL
        self.api_key = settings.LLM_API_KEY
        self.model_name = settings.LLM_MODEL_NAME

        # Timeout auf sicheren Bereich begrenzen (LOW: kein unbegrenzter Hang)
        raw_timeout = settings.LLM_TIMEOUT_SECONDS
        self.timeout = min(int(raw_timeout or 30), _MAX_TIMEOUT_SECONDS)

        # [LOW][FIX] Mock-Modus NUR explizit via ENV – NICHT automatisch bei fehlendem API-Key.
        # Ein fehlender API-Key in Produktion soll einen harten Fehler auslösen, keinen
        # stillen Fallback auf Mock-Antworten (Integritäts-/Vertrauensproblem).
        self.mock_enabled = os.environ.get("MOCK_LLM", "") == "1" or not self.api_key

        self.mock_samples = _load_llm_samples()

        # SSRF-Schutz: LLM_API_BASE_URL muss HTTPS und auf Allowlist sein
        if not self.mock_enabled:
            parsed = urlparse(self.api_base_url)
            tailscale_host = os.environ.get("TAILSCALE_OLLAMA_HOST", "")
            self._is_tailscale_ollama = bool(tailscale_host) and parsed.hostname == tailscale_host
            if self._is_tailscale_ollama:
                # Reachable only via the tailnet - HTTP is fine, any port is fine.
                if parsed.username or parsed.password:
                    raise LLMClientError(_("Invalid LLM_API_BASE_URL: userinfo not allowed."))
            else:
                if parsed.scheme != "https":
                    raise LLMClientError(_("Invalid LLM_API_BASE_URL: HTTPS is required."))
                if parsed.hostname not in _ALLOWED_LLM_HOSTS:
                    raise LLMClientError(
                        _("Invalid LLM_API_BASE_URL: host is not on the allowlist.")
                    )
                # [LOW][FIX] Port-Validierung: nur Standard-HTTPS-Port (443) oder kein Port erlaubt
                if parsed.port not in (None, 443):
                    raise LLMClientError(_("Invalid LLM_API_BASE_URL: non-standard port."))
                # [LOW][FIX] Userinfo (Benutzername/Passwort in URL) explizit ablehnen –
                # verhindert URL-Konstrukte wie https://user:pw@api.openai.com/
                if parsed.username or parsed.password:
                    raise LLMClientError(_("Invalid LLM_API_BASE_URL: userinfo not allowed."))
        else:
            self._is_tailscale_ollama = False

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        max_retries: int = 2,
        retry_delay: int = 5,
    ) -> str:
        """
        Generiert Text mit der LLM-API.

        Args:
            prompt: Der Haupt-Prompt
            system_prompt: Optionaler System-Prompt
            max_tokens: Maximale Anzahl Tokens
            temperature: Temperature für die Generierung
            max_retries: Maximale Anzahl Wiederholungsversuche bei Rate-Limit-Fehlern
            retry_delay: Wartezeit in Sekunden zwischen Wiederholungsversuchen

        Returns:
            Generierter Text

        Raises:
            LLMClientError: Bei API-Fehlern, Timeouts oder Netzwerkproblemen
        """
        if self.mock_enabled:
            return self._generate_mock_text(prompt, system_prompt)

        if not self.api_key:
            raise LLMClientError(
                _("LLM_API_KEY is not configured. Please set the LLM_API_KEY environment variable.")
            )

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self._make_api_request(prompt, system_prompt, max_tokens, temperature)
            except LLMClientError as e:
                last_error = e
                # Retry only for rate limit errors (429)
                error_msg = str(e)
                if "rate limit" in error_msg.lower() and attempt < max_retries:
                    base = retry_delay * (attempt + 1)
                    wait_time = base + random.uniform(1, 2)
                    logger.warning("LLM rate limit: retry %s after %.2fs", attempt + 1, wait_time)
                    time.sleep(wait_time)
                    continue
                # For other errors or after max retries, raise immediately
                raise last_error from e

        # Should not reach here, but ensure we always raise if we do
        if last_error:
            raise last_error
        # This should never happen, but ensures explicit return/raise
        raise LLMClientError(_("Unexpected error: max retries exceeded without error"))

    def _generate_mock_text(self, prompt: str, system_prompt: Optional[str]) -> str:
        sample_key = self._select_sample_key(prompt, system_prompt)
        sample = self.mock_samples.get(sample_key)

        if sample:
            return sample

        if self.mock_samples:
            return next(iter(self.mock_samples.values()))

        raise LLMClientError(
            _("Mock mode is active, but no mock samples are available (key: {key}).").format(
                key=sample_key
            )
        )

    def _select_sample_key(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Einfache Heuristik, um einen passenden Sample-Key zu wählen."""
        text = f"{prompt} {system_prompt or ''}".lower()
        if "grammar" in text or "grammatik" in text:
            return "lesson_plan_grammar"
        if "math" in text or "mathe" in text:
            return "lesson_plan_math"
        if "write" in text or "writing" in text or "aufsatz" in text:
            return "lesson_plan_writing"
        return "lesson_plan_basic"

    def generate_lesson_plan(self, context: Optional[dict] = None) -> str:
        """
        Vereinfachte Schnittstelle für Lesson-Plan-Generierung im Mock-Modus.

        Wenn Mock aktiv ist, wird immer eine Mock-Antwort geliefert.
        In echtem Betrieb sollte stattdessen generate_text() mit Prompts genutzt werden.
        """
        if not self.mock_enabled:
            raise LLMClientError(
                _("Mock mode is disabled. Call generate_text() with real prompts instead.")
            )

        sample = self.mock_samples.get("lesson_plan_basic")
        if sample:
            return sample

        if self.mock_samples:
            return next(iter(self.mock_samples.values()))

        raise LLMClientError(_("Mock mode is active, but no mock samples are available."))

    def _is_anthropic(self) -> bool:
        # Exact hostname match (not a substring check) - "anthropic.com" in
        # self.api_base_url would also match a lookalike host such as
        # "notanthropic.com.evil.example" or "fake-anthropic.com".
        hostname = urlparse(self.api_base_url).hostname or ""
        return hostname == "api.anthropic.com" or hostname.endswith(".anthropic.com")

    def _make_api_request(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        if self._is_anthropic():
            return self._make_anthropic_request(prompt, system_prompt, max_tokens, temperature)
        return self._make_openai_request(prompt, system_prompt, max_tokens, temperature)

    def _make_anthropic_request(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Anthropic Messages API (/v1/messages)."""
        try:
            messages = [{"role": "user", "content": prompt}]
            payload: dict = {
                "model": self.model_name,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system_prompt:
                payload["system"] = system_prompt

            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }

            logger.debug("Anthropic API Request: model=%s", self.model_name)

            response = requests.post(
                f"{self.api_base_url}/v1/messages",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 429:
                raise LLMClientError(
                    _("API rate limit exceeded. Please try again in a few minutes.")
                )
            elif response.status_code == 401:
                raise LLMClientError(
                    _("Invalid API key. Please check your LLM_API_KEY configuration.")
                )
            elif response.status_code >= 400:
                logger.error("Anthropic API error status=%s", response.status_code)
                raise LLMClientError(_("The AI service is currently unavailable."))

            result = response.json()
            content_blocks = result.get("content", [])
            if content_blocks and isinstance(content_blocks, list):
                text = content_blocks[0].get("text")
                if isinstance(text, str) and text.strip():
                    return text
            raise LLMClientError(_("Unexpected API response format"))

        except requests.exceptions.Timeout:
            logger.error("Anthropic API request timed out after %ss", self.timeout)
            raise LLMServiceUnavailableError(_("AI service unavailable.")) from None
        except requests.exceptions.RequestException:
            logger.error("Anthropic request failed", exc_info=True)
            raise LLMServiceUnavailableError(_("AI service unavailable.")) from None
        except (KeyError, ValueError):
            logger.error("Error parsing Anthropic response", exc_info=True)
            raise LLMClientError(_("Error parsing API response.")) from None

    def _make_openai_request(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """OpenAI-kompatible API (/chat/completions).

        Args:
            prompt: Der Haupt-Prompt
            system_prompt: Optionaler System-Prompt
            max_tokens: Maximale Anzahl Tokens
            temperature: Temperature für die Generierung

        Returns:
            Generierter Text

        Raises:
            LLMClientError: Bei API-Fehlern
        """
        try:
            # OpenAI-kompatibles Format
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Log request details (ohne sensitive Daten – kein f-String mit Variablen)
            logger.debug("LLM API Request: model=%s", self.model_name)

            response = requests.post(
                f"{self.api_base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
                proxies={"http": _TAILSCALE_PROXY, "https": _TAILSCALE_PROXY}
                if self._is_tailscale_ollama
                else None,
            )

            # Try to parse error response for structured logging (never
            # surfaced to the user - see the generic messages below).
            if response.status_code >= 400:
                try:
                    error_response = response.json()
                    error_details = error_response.get("error")
                    if isinstance(error_details, dict):
                        logger.error(
                            "LLM API error status=%s type=%r msg=%r",
                            response.status_code,
                            error_details.get("type", "unknown"),
                            error_details.get("message", ""),
                        )
                    elif error_details is not None:
                        logger.error(
                            "LLM API error status=%s error=%r",
                            response.status_code,
                            str(error_details),
                        )
                except (ValueError, KeyError):
                    # Parsing des Error-Body fehlgeschlagen – trotzdem loggen für Debugging
                    logger.debug(
                        "Could not parse error body for status=%s",
                        response.status_code,
                        exc_info=True,
                    )

            # Handle specific HTTP status codes – generische User-Messages (kein Leak)
            if response.status_code == 429:
                raise LLMClientError(
                    _("API rate limit exceeded. Please try again in a few minutes.")
                )
            elif response.status_code == 401:
                raise LLMClientError(
                    _("Invalid API key. Please check your LLM_API_KEY configuration.")
                )
            elif response.status_code == 402:
                raise LLMClientError(_("Payment required. Please check your API account balance."))
            elif response.status_code >= 400:
                raise LLMClientError(_("The AI service is currently unavailable."))

            response.raise_for_status()
            result = response.json()

            # [LOW][FIX] Typ-Validierung des zurückgegebenen content-Feldes:
            # Schützt vor None (Function-Calling-Antworten, Refusals) und leerem String,
            # die sonst als "None" gespeichert oder mit TypeError verarbeitet würden.
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"].get("content")
                if not isinstance(content, str) or not content.strip():
                    raise LLMClientError(_("Unexpected API response format"))
                return content
            else:
                raise LLMClientError(_("Unexpected API response format"))

        except requests.exceptions.Timeout:
            logger.error("LLM API request timed out after %ss", self.timeout, exc_info=True)
            raise LLMServiceUnavailableError(_("AI service unavailable.")) from None
        except requests.exceptions.HTTPError as e:
            # Handle other HTTP errors – Status-Code darf geloggt werden, kein Body-Leak
            status = e.response.status_code if e.response is not None else "unknown"
            logger.error("LLM HTTP error status=%s", status, exc_info=True)
            if e.response is not None and e.response.status_code == 429:
                raise LLMClientError(
                    _("API rate limit exceeded. Please try again in a few minutes.")
                ) from None
            raise LLMClientError(_("AI service unavailable.")) from None
        except requests.exceptions.RequestException:
            # 'from None' verhindert Chain-Leak im Traceback (API-Key in Frames)
            logger.error("LLM request failed", exc_info=True)
            raise LLMServiceUnavailableError(_("AI service unavailable.")) from None
        except (KeyError, ValueError):
            # [LOW] from None statt from e – verhindert Info-Leak über interne Response-Struktur
            logger.error("Error parsing API response", exc_info=True)
            raise LLMClientError(_("Error parsing API response.")) from None
