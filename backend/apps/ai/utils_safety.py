"""
Hilfsfunktionen für Privacy/PII-Schutz im AI-Kontext.
"""

import re
from copy import deepcopy
from typing import Any, Dict

PII_KEYS = {"full_name", "address", "email", "phone", "tax_id", "dob", "medical_info"}
REDACTED = "[REDACTED]"
FILTERED = "[FILTERED]"
MAX_CONTEXT_STRING_LEN = 2000

# Regex patterns to catch obvious emails/phone numbers in uncontrolled strings.
# Rules to stay non-polynomial (CodeQL py/polynomial-redos):
#   - No dot inside quantified character classes; dot appears only as a literal separator.
#   - All repetition quantifiers are bounded.
#   - Character sets across adjacent quantifiers are disjoint.
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9_%+\-]{1,64}"  # local part (no dot in char class)
    r"(?:\.[A-Za-z0-9_%+\-]{1,64}){0,5}"  # optional dot-separated segments
    r"@"
    r"[A-Za-z0-9\-]{1,63}"  # first domain label (no dot)
    r"(?:\.[A-Za-z0-9\-]{1,63}){0,10}"  # additional labels
    r"\.[A-Za-z]{2,7}"  # TLD
)
PHONE_PATTERN = re.compile(r"\+?[0-9]{1,4}(?:[\s.\-][0-9]{1,4}){2,14}")

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(?:(?:all|previous|prior|above)\s+){0,3}instructions"
    r"|override\s+(?:(?:all|previous|prior)\s+)?instructions"
    r"|^system\s*:"
    r"|<system>"
    r"|\[INST\]"
    r"|\[/INST\]"
    r"|###"
    r"|you\s+are\s+now"
    r"|act\s+as"
    r"|pretend\s+(?:you\s+are|to\s+be)"
    r"|roleplay\s+as",
    re.IGNORECASE | re.MULTILINE,
)


def strip_injection_patterns(text: str) -> str:
    text = text[:MAX_CONTEXT_STRING_LEN]
    text = _CONTROL_CHARS.sub("", text)
    text = _INJECTION_PATTERNS.sub(FILTERED, text)
    return text


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (REDACTED if key in PII_KEYS else _sanitize_value(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        masked = strip_injection_patterns(value)
        # Mask obvious email/phone occurrences inline.
        masked = EMAIL_PATTERN.sub(REDACTED, masked)
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
