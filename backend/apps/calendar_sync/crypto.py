"""
Encrypt/decrypt CalDAV app-specific passwords at rest.

Uses a dedicated CALDAV_ENCRYPTION_KEY (Fernet, symmetric) rather than
reusing SECRET_KEY - a real third-party credential (the tutor's Apple/
Google app-specific password) shouldn't share a key with Django's session/
CSRF signing, so rotating one never silently affects the other.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CalendarCredentialError(Exception):
    """Raised when CALDAV_ENCRYPTION_KEY is missing or a stored credential
    can't be decrypted with it (e.g. the key was rotated)."""

    pass


def _get_fernet() -> Fernet:
    key = getattr(settings, "CALDAV_ENCRYPTION_KEY", "") or ""
    if not key:
        raise CalendarCredentialError("CALDAV_ENCRYPTION_KEY is not configured.")
    key_bytes = key.encode() if isinstance(key, str) else key
    try:
        return Fernet(key_bytes)
    except (ValueError, TypeError) as e:
        raise CalendarCredentialError("CALDAV_ENCRYPTION_KEY is not a valid Fernet key.") from e


def encrypt_password(raw_password: str) -> bytes:
    return _get_fernet().encrypt(raw_password.encode())


def decrypt_password(encrypted: bytes) -> str:
    try:
        return _get_fernet().decrypt(bytes(encrypted)).decode()
    except InvalidToken as e:
        raise CalendarCredentialError(
            "Stored CalDAV password could not be decrypted (wrong key?)."
        ) from e
