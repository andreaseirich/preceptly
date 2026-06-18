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
    # --- Englisch ---
    r"ignore\s+(?:(?:all|previous|prior|above)\s+){0,3}instructions"
    r"|override\s+(?:(?:all|previous|prior)\s+)?instructions"
    r"|disregard\s+(?:(?:all|previous|prior|above)\s+){0,3}instructions"
    r"|forget\s+(?:(?:all|previous|prior|above)\s+){0,3}(?:instructions|prompts?)"
    r"|^system\s*:"
    r"|<system>"
    r"|<\|system\|>"
    r"|\[INST\]"
    r"|\[/INST\]"
    r"|###"
    r"|you\s+are\s+now"
    r"|act\s+as"
    r"|pretend\s+(?:you\s+are|to\s+be)"
    r"|roleplay\s+as"
    r"|new\s+(?:task|instructions?|prompt)"
    r"|system\s+prompt"
    # --- Deutsch ---
    r"|ignoriere\s+(?:(?:alle|alle\s+vorherigen|vorherige|obige|bisherige)\s+){0,3}(?:anweisungen|anleitungen|befehle|regeln)"
    r"|anweisungen\s+ignorieren"
    r"|vergiss\s+(?:(?:alle|alle\s+vorherigen|vorherige|obige|bisherige)\s+){0,3}(?:anweisungen|anleitungen|befehle|regeln|prompts?)"
    r"|verwerfe\s+(?:(?:alle|alle\s+vorherigen|vorherige|obige|bisherige)\s+){0,3}(?:anweisungen|anleitungen|befehle|regeln)"
    r"|missachte\s+(?:(?:alle|alle\s+vorherigen|vorherige|obige|bisherige)\s+){0,3}(?:anweisungen|anleitungen|befehle|regeln)"
    r"|überschreibe\s+(?:(?:alle|alle\s+vorherigen|vorherige|obige)\s+){0,3}(?:anweisungen|anleitungen|befehle|regeln)"
    r"|du\s+bist\s+(?:jetzt|nun|ab\s+(?:jetzt|sofort))"
    r"|ab\s+jetzt\s+bist\s+du"
    r"|spiele\s+(?:die\s+rolle|jetzt)"
    r"|verhalte\s+dich\s+(?:wie|als)"
    r"|tue\s+so,?\s+als\s+(?:ob|wärst)"
    r"|gib\s+dich\s+als"
    r"|neue\s+(?:aufgabe|anweisung(?:en)?|rolle)"
    r"|system[-\s]?prompt",
    re.IGNORECASE | re.MULTILINE,
)


def strip_injection_patterns(text: str) -> str:
    import unicodedata

    text = text[:MAX_CONTEXT_STRING_LEN]
    # 1. Normalisiere Unicode (NFKC) — fängt Homoglyphen/Compat-Zeichen ab.
    text = unicodedata.normalize("NFKC", text)
    # 2. Entferne Zero-Width-Chars und bidi-Steuerzeichen.
    text = re.sub(r"[\u200b-\u200f\u202a-\u202f\ufeff]", "", text)
    # 3. Entferne Steuerzeichen.
    text = _CONTROL_CHARS.sub("", text)
    # 4. Filtere bekannte Injection-Phrasen (EN + DE).
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


def wrap_untrusted(text: str) -> str:
    """
    Bettet nicht vertrauenswürdigen User-Input in einen klar markierten Block ein,
    damit nachgelagerte Modelle ihn nicht als System-Anweisung interpretieren.

    Defense-in-Depth: zusätzlich zu strip_injection_patterns().
    """
    if text is None:
        return "<user_provided_untrusted></user_provided_untrusted>"
    sanitized = strip_injection_patterns(str(text))
    # Verhindere, dass der Input selbst die Tags schließt.
    sanitized = sanitized.replace("</user_provided_untrusted>", FILTERED)
    sanitized = sanitized.replace("<user_provided_untrusted>", FILTERED)
    return f"<user_provided_untrusted>\n{sanitized}\n</user_provided_untrusted>"
