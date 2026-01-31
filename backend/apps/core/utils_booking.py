"""
Utilities for public booking - resolve tutor from token.
"""

import secrets

from apps.core.models import UserProfile
from django.contrib.auth.models import User


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
    if tutor_token:
        try:
            profile = UserProfile.objects.get(public_booking_token=tutor_token)
            return profile.user
        except UserProfile.DoesNotExist:
            pass
    return None


def ensure_public_booking_token(profile: UserProfile) -> str:
    """
    Ensures the UserProfile has a public_booking_token. Creates one if missing.

    Returns:
        The (possibly newly generated) token
    """
    if not profile.public_booking_token:
        profile.public_booking_token = secrets.token_urlsafe(32)
        profile.save(update_fields=["public_booking_token"])
    return profile.public_booking_token
