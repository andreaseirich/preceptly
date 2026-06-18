"""
Utilities for public booking - resolve tutor from token.
"""

import secrets

from django.contrib.auth.models import User
from django.db import transaction

from apps.core.models import UserProfile

MIN_TOKEN_LEN = 32
MAX_TOKEN_LEN = 128


def get_tutor_for_booking(tutor_token: str | None = None) -> User | None:
    """
    Resolves the tutor User for public booking.

    When tutor_token is provided and matches a UserProfile.public_booking_token,
    returns that user. Otherwise returns None (multi-tenancy: no shared fallback).

    Args:
        tutor_token: Token from URL or request body (required for public booking)

    Returns:
        User instance or None if token is missing/invalid
    """
    if not tutor_token:
        return None
    if len(tutor_token) < MIN_TOKEN_LEN or len(tutor_token) > MAX_TOKEN_LEN:
        return None
    try:
        profile = UserProfile.objects.select_related("user").get(public_booking_token=tutor_token)
        return profile.user
    except UserProfile.DoesNotExist:
        return None


def ensure_public_booking_token(profile: UserProfile) -> str:
    """
    Ensures the UserProfile has a public_booking_token. Creates one if missing.
    Uses select_for_update() to prevent race conditions in concurrent requests.

    Returns:
        The (possibly newly generated) token
    """
    with transaction.atomic():
        locked = UserProfile.objects.select_for_update().get(pk=profile.pk)
        if not locked.public_booking_token:
            locked.public_booking_token = secrets.token_urlsafe(32)
            locked.save(update_fields=["public_booking_token"])
        return locked.public_booking_token
