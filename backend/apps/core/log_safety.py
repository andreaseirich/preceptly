"""
Shared helper to neutralize log injection: strips control characters
(CR/LF and other C0 controls) from request-derived values before they
reach a log call, so an attacker cannot forge fake log lines by putting
"\\n2026-01-01 FAKE ADMIN LOGIN" etc. into a header/query/body value.

Prefer this over relying on %r/repr() in the format string - it is an
explicit sanitizer CodeQL's log-injection query recognizes, whereas %r's
implicit escaping is not reliably modeled as sanitization.
"""

import re

_CONTROL_CHARS_RE = re.compile(r"[\r\n\x00-\x1f]")


def safe_log_value(value, max_len: int = 200) -> str:
    """Returns `value` as a string with control characters stripped and
    length capped, safe to interpolate into a log message."""
    text = "" if value is None else str(value)
    return _CONTROL_CHARS_RE.sub("", text)[:max_len]
