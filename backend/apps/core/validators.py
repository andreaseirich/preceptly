"""Validators for billing profile fields."""

import re


def validate_billing_tax_number(value: str) -> str | None:
    """
    Validate German Steuernummer or USt-IdNr.

    Returns an error message string on failure, None if valid.
    """
    if not value:
        return None
    cleaned = re.sub(r"[\s/\-]", "", value.upper())
    if re.match(r"^DE\d{9}$", cleaned):
        return None
    if re.match(r"^\d{10,13}$", cleaned):
        return None
    return (
        "Ungültiges Format. Akzeptiert werden Steuernummer (z. B. 123/456/78901) "
        "oder USt-IdNr. (z. B. DE123456789)."
    )
