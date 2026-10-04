"""Mindestabstand des Tutors zwischen Terminen (UserProfile.min_gap_minutes)."""


def min_gap_minutes(user) -> int:
    """Mindestabstand in Minuten, 0 wenn nichts eingestellt ist oder es kein Profil gibt."""
    profile = getattr(user, "profile", None)
    return int(getattr(profile, "min_gap_minutes", 0) or 0)
