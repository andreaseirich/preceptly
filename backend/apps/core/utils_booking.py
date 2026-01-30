"""
Utilities for public booking - resolve tutor from token.
"""

from apps.core.models import UserProfile
from django.contrib.auth.models import User


def get_tutor_for_booking(tutor_token: str | None = None) -> User | None:
    """
    Resolves the tutor User for public booking.

    When tutor_token is provided and matches a UserProfile.public_booking_token,
    returns that user. Otherwise returns the first user (for backward compatibility).

    Args:
        tutor_token: Optional token from URL or request body

    Returns:
        User instance or None if no user exists
    """
    if tutor_token:
        try:
            profile = UserProfile.objects.get(public_booking_token=tutor_token)
            return profile.user
        except UserProfile.DoesNotExist:
            pass
    return User.objects.order_by("id").first()
