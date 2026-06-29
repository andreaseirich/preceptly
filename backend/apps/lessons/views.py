"""
Views module for lessons.

This module re-exports views from their domain-specific modules to maintain
backward compatibility with existing imports.
"""

# Re-export for backward compatibility
# ruff: noqa: F401
from apps.lessons.views_calendar import CalendarView, LessonMonthView, WeekView
from apps.lessons.views_conflicts import ConflictDetailView
from apps.lessons.views_crud import (
    LessonCreateView,
    LessonDeleteView,
    LessonDetailView,
    LessonListView,
    LessonRescheduleView,
    LessonUpdateView,
)

__all__ = [
    "LessonListView",
    "LessonCreateView",
    "LessonUpdateView",
    "LessonDetailView",
    "LessonDeleteView",
    "LessonMonthView",
    "WeekView",
    "CalendarView",
    "ConflictDetailView",
]
