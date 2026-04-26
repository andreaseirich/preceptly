"""
Hilfsfunktionen für Privacy/PII-Schutz im AI-Kontext.
"""

import re
from copy import deepcopy
from typing import Any, Dict

PII_KEYS = {"full_name", "address", "email", "phone", "tax_id", "dob", "medical_info"}
REDACTED = "[REDACTED]"

# Simple regex patterns to catch obvious emails/phone numbers even if keys are unknown.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?\d[\s.-]?){7,}\d")


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (REDACTED if key in PII_KEYS else _sanitize_value(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        # Mask obvious email/phone occurrences inline.
        masked = EMAIL_PATTERN.sub(REDACTED, value)
        masked = PHONE_PATTERN.sub(REDACTED, masked)
        return masked
    return value


def sanitize_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entfernt oder pseudonymisiert PII aus einem Kontext-Dict.

    Bekannte PII-Felder werden durch "[REDACTED]" ersetzt.
    Beispiel: {"contact": "john@example.com", "notes": "+49 151 2345678"} -> "[REDACTED]"
    """
    safe_copy = deepcopy(ctx)
    return _sanitize_value(safe_copy)
