"""
Backward compatibility module for services.

This module re-exports services from their new locations to maintain
backward compatibility with existing imports.
"""

# Re-export for backward compatibility
from apps.lessons.conflict_service import (
    SessionConflictService,
    recalculate_conflicts_for_affected_sessions,
    recalculate_conflicts_for_blocked_time,
    LessonConflictService,
    recalculate_conflicts_for_affected_lessons,
)
from apps.lessons.query_service import SessionQueryService, LessonQueryService

__all__ = [
    "SessionConflictService",
    "SessionQueryService",
    "recalculate_conflicts_for_affected_sessions",
    "recalculate_conflicts_for_blocked_time",
    # Backwards compatibility aliases
    "LessonConflictService",
    "LessonQueryService",
    "recalculate_conflicts_for_affected_lessons",
]
