"""
High-level service for lesson plan generation.
"""

from typing import Any, Dict, Optional

from apps.ai.client import LLMClient, LLMClientError
from apps.ai.prompts import build_lesson_plan_prompt, extract_subject_from_student
from apps.ai.utils_safety import sanitize_context
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Session
from django.conf import settings
from django.utils.translation import gettext_lazy as _


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
        student = session.contract.student

        # Get previous sessions (max. 5, sorted by date)
        previous_sessions = Session.objects.filter(
            contract__student=student, date__lt=session.date
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
                "email": student.email or "",
                "phone": student.phone or "",
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

    def generate_lesson_plan(self, session: Session) -> LessonPlan:
        """
        Generates an AI lesson plan for a session.

        Args:
            session: Session object

        Returns:
            LessonPlan object

        Raises:
            LessonPlanGenerationError: On generation errors
        """
        # Gather context and apply PII protection
        raw_context = self.gather_context(session)
        safe_context = sanitize_context(raw_context)

        # Build prompt
        system_prompt, user_prompt = build_lesson_plan_prompt(session, safe_context)

        # Call LLM
        try:
            generated_content = self.client.generate_text(
                prompt=user_prompt, system_prompt=system_prompt, max_tokens=1500, temperature=0.7
            )
        except LLMClientError as e:
            raise LessonPlanGenerationError(_("LLM error: {error}").format(error=str(e))) from e

        # Create or update LessonPlan
        student = session.contract.student
        subject = extract_subject_from_student(student)

        lesson_plan, created = LessonPlan.objects.update_or_create(
            lesson=session,
            defaults={
                "student": student,
                "topic": _("Lesson plan for {date}").format(date=session.date),
                "subject": subject,
                "content": generated_content,
                "grade_level": student.grade or "",
                "duration_minutes": session.duration_minutes,
                "llm_model": settings.LLM_MODEL_NAME,
            },
        )

        return lesson_plan
