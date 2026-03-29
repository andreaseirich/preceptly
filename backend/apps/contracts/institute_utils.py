"""
Match contract.institute (free text) for institute-specific billing rules.
"""

from __future__ import annotations

TUTORSPACE_INSTITUTE_NAME = "TutorSpace"
ABACUS_INSTITUTE_NAME = "Abacus"


def _norm(institute: str | None) -> str:
    return (institute or "").strip().lower()


def is_tutorspace_institute(institute: str | None) -> bool:
    return _norm(institute) == TUTORSPACE_INSTITUTE_NAME.lower()


def is_abacus_institute(institute: str | None) -> bool:
    return _norm(institute) == ABACUS_INSTITUTE_NAME.lower()
