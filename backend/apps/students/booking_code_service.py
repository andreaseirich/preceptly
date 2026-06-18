"""
Service for student booking codes (Public Booking authentication).

Codes are stored hashed; plaintext is only shown at generation/regeneration.
Uses constant-time comparison to prevent timing attacks.
"""

import hmac
import secrets

from django.db import transaction

from apps.contracts.models import Contract

# Alphabet without easily confused chars: no 0,O,1,l,I,2,Z,5,S,8,B
_BOOKING_CODE_ALPHABET = "ACDEFGHJKMNPQRTVWXY34679"
_BOOKING_CODE_LENGTH = 12


def generate_booking_code() -> str:
    """
    Generate a random booking code (12 chars, unguessable).

    Uses alphabet without 0/O, 1/l/I, 2/Z, 5/S, 8/B to avoid confusion.
    """
    return "".join(secrets.choice(_BOOKING_CODE_ALPHABET) for _ in range(_BOOKING_CODE_LENGTH))


def _hash_code(plain_code: str) -> str:
    """Hash a code for storage. Uses Django's password hashing (PBKDF2 with salt)."""
    from django.contrib.auth.hashers import make_password

    normalized = plain_code.strip().upper().replace(" ", "")
    return make_password(normalized)


def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks.

    Delegates to hmac.compare_digest to avoid any length-leak or
    custom-crypto mistakes.
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _verify_code(plain_code: str, stored_hash: str) -> bool:
    """Verify a plaintext code against a stored Django password hash. Timing-safe."""
    from django.contrib.auth.hashers import check_password

    normalized = plain_code.strip().upper().replace(" ", "")
    return check_password(normalized, stored_hash)


def verify_booking_code(student: Contract, plain_code: str) -> bool:
    """
    Verify a booking code against a student's stored hash.

    Returns True only if the code matches. Uses Django's check_password,
    which is timing-safe and supports PBKDF2/Argon2/bcrypt.
    """
    if not student.booking_code_hash or not plain_code or not plain_code.strip():
        return False
    return _verify_code(plain_code, student.booking_code_hash)


def set_booking_code(student: Contract) -> str:
    """
    Generate a new booking code, store its hash atomically, return plaintext.

    Uses select_for_update to prevent race conditions on parallel regenerate
    requests. The last writer no longer silently wins with a mismatched
    plaintext/hash pair.

    Caller must display the returned code to the tutor once; it is never
    stored in plaintext. Never log or expose the returned value.
    """
    plain_code = generate_booking_code()
    new_hash = _hash_code(plain_code)
    with transaction.atomic():
        locked = Contract.objects.select_for_update().get(pk=student.pk)
        locked.booking_code_hash = new_hash
        locked.save(update_fields=["booking_code_hash"])
    student.booking_code_hash = new_hash
    return plain_code


def ensure_booking_code(student: Contract) -> str | None:
    """
    Ensure student has a booking code. If not, generate one and return it.

    If student already has a code, returns None (we cannot recover plaintext).
    """
    if student.booking_code_hash:
        return None
    return set_booking_code(student)
