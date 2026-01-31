"""
Service for student booking codes (Public Booking authentication).

Codes are stored hashed; plaintext is only shown at generation/regeneration.
Uses constant-time comparison to prevent timing attacks.
"""

import hashlib
import secrets

from apps.students.models import Student

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
    """Hash a code for storage. Uses SHA-256."""
    normalized = plain_code.strip().upper().replace(" ", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode("utf-8"), b.encode("utf-8"), strict=True):
        result |= x ^ y
    return result == 0


def verify_booking_code(student: Student, plain_code: str) -> bool:
    """
    Verify a booking code against a student's stored hash.

    Returns True only if the code matches. Uses constant-time comparison.
    """
    if not student.booking_code_hash or not plain_code or not plain_code.strip():
        return False
    input_hash = _hash_code(plain_code)
    return _constant_time_compare(student.booking_code_hash, input_hash)


def set_booking_code(student: Student) -> str:
    """
    Generate a new booking code, store its hash, return plaintext.

    Caller must display the returned code to the tutor once; it is never
    stored in plaintext. Never log or expose the returned value.
    """
    plain_code = generate_booking_code()
    student.booking_code_hash = _hash_code(plain_code)
    student.save(update_fields=["booking_code_hash"])
    return plain_code


def ensure_booking_code(student: Student) -> str | None:
    """
    Ensure student has a booking code. If not, generate one and return it.

    If student already has a code, returns None (we cannot recover plaintext).
    """
    if student.booking_code_hash:
        return None
    return set_booking_code(student)
