"""
High-level service for lesson plan generation.
"""

from typing import Any, Dict, Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.ai.client import LLMClient, LLMClientError
from apps.ai.prompts import build_lesson_plan_prompt, extract_subject_from_student
from apps.ai.utils_safety import sanitize_context, strip_injection_patterns
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Session


class LessonPlanGenerationError(Exception):
    """Exception for errors in lesson plan generation."""

    pass


class LessonPlanService:
    """Service for generating AI lesson plans."""

    def __init__(self, client: Optional[LLMClient] = None):
        """
        Initializes the service.

        Args:
            client: Optional LLM client (for tests/mocking)
        """
        self.client = client or LLMClient()

    def gather_context(self, session: Session) -> Dict[str, Any]:
        """
        Gathers context information for prompt generation.

        Args:
            session: Session object

        Returns:
            Dict with context information
        """
        student = session.contract

        # Get previous sessions (max. 5, sorted by date)
        previous_sessions = Session.objects.filter(
            contract=student, date__lt=session.date
        ).order_by("-date")[:5]

        previous_sessions_data = [
            {
                "date": prev_session.date.isoformat(),
                "notes": prev_session.notes or "",
                "status": prev_session.get_status_display(),
            }
            for prev_session in previous_sessions
        ]

        return {
            "student": {
                "full_name": f"{student.first_name} {student.last_name}".strip(),
                "address": student.school or "",
                "tax_id": "",
                "dob": "",
                "medical_info": "",
                "grade": student.grade or "",
                "subjects": student.subjects or "",
                "notes": student.notes or "",
            },
            "lesson": {
                "date": session.date.isoformat(),
                "duration_minutes": session.duration_minutes,
                "status": session.get_status_display(),
                "notes": session.notes or "",
            },
            "contract": {"unit_duration_minutes": session.contract.unit_duration_minutes},
            "previous_lessons": previous_sessions_data,
        }

    def generate_lesson_plan(self, session: Session, user=None) -> LessonPlan:
        """
        Generates an AI lesson plan for a session.

        Args:
            session: Session object
            user: Optional user for ownership check

        Returns:
            LessonPlan object

        Raises:
            PermissionDenied: If user does not own the session
            LessonPlanGenerationError: On generation errors
        """
        # Ownership-Check: Session muss dem aufrufenden User gehören
        if user is not None and session.contract.user_id != user.id:
            raise PermissionDenied("Session does not belong to user.")

        # Gather context and apply PII protection
        raw_context = self.gather_context(session)
        safe_context = sanitize_context(raw_context)

        # Build prompt
        system_prompt, user_prompt = build_lesson_plan_prompt(session, safe_context)

        # Race-Condition-Schutz: atomic + select_for_update verhindert doppelte LLM-Calls
        with transaction.atomic():
            existing = LessonPlan.objects.select_for_update().filter(lesson=session).first()
            if existing is not None:
                # Bereits ein aktueller Plan vorhanden – direkt zurückgeben
                return existing

            # Call LLM (außerhalb des Lock-Bereichs wäre besser für Performance,
            # aber innerhalb der Transaktion sichert uns gegen Race Conditions ab)
            try:
                generated_content = self.client.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=1500,
                    temperature=0.7,
                )
            except LLMClientError as e:
                raise LessonPlanGenerationError(
                    _("The lesson plan could not be generated. Please try again.")
                ) from e

            # Sanitize subject: strip injection patterns + length limit
            student = session.contract
            raw_subject = extract_subject_from_student(student)
            subject = strip_injection_patterns(raw_subject)[:100]

            lesson_plan, created = LessonPlan.objects.update_or_create(
                lesson=session,
                defaults={
                    "contract": student,
                    "topic": _("Lesson plan for {date}").format(date=session.date),
                    "subject": subject,
                    "content": generated_content,
                    "grade_level": student.grade or "",
                    "duration_minutes": session.duration_minutes,
                    "llm_model": settings.LLM_MODEL_NAME,
                },
            )

        return lesson_plan
