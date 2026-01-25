"""
High-Level-Service für LessonPlan-Generierung.
"""

from typing import Any, Dict, Optional

from apps.ai.client import LLMClient, LLMClientError
from apps.ai.prompts import build_lesson_plan_prompt, extract_subject_from_student
from apps.ai.utils_safety import sanitize_context
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Lesson
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class LessonPlanGenerationError(Exception):
    """Exception for errors in lesson plan generation."""

    pass


class LessonPlanService:
    """Service für die Generierung von KI-Unterrichtsplänen."""

    def __init__(self, client: Optional[LLMClient] = None):
        """
        Initialisiert den Service.

        Args:
            client: Optional LLM-Client (für Tests/Mocking)
        """
        self.client = client or LLMClient()

    def gather_context(self, lesson: Lesson) -> Dict[str, Any]:
        """
        Sammelt Kontext-Informationen für die Prompt-Generierung.

        Args:
            lesson: Lesson-Objekt

        Returns:
            Dict mit Kontext-Informationen
        """
        student = lesson.contract.student

        # Hole vorherige Lessons (max. 5, sortiert nach Datum)
        previous_lessons = Lesson.objects.filter(
            contract__student=student, date__lt=lesson.date
        ).order_by("-date")[:5]

        previous_lessons_data = [
            {
                "date": prev_lesson.date.isoformat(),
                "notes": prev_lesson.notes or "",
                "status": prev_lesson.get_status_display(),
            }
            for prev_lesson in previous_lessons
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
                "date": lesson.date.isoformat(),
                "duration_minutes": lesson.duration_minutes,
                "status": lesson.get_status_display(),
                "notes": lesson.notes or "",
            },
            "contract": {"unit_duration_minutes": lesson.contract.unit_duration_minutes},
            "previous_lessons": previous_lessons_data,
        }

    def generate_lesson_plan(self, lesson: Lesson) -> LessonPlan:
        """
        Generiert einen KI-Unterrichtsplan für eine Lesson.

        Args:
            lesson: Lesson-Objekt

        Returns:
            LessonPlan-Objekt

        Raises:
            LessonPlanGenerationError: Bei Fehlern bei der Generierung
        """
        # Sammle Kontext und wende PII-Schutz an
        raw_context = self.gather_context(lesson)
        safe_context = sanitize_context(raw_context)

        # Baue Prompt
        system_prompt, user_prompt = build_lesson_plan_prompt(lesson, safe_context)

        # Rufe LLM auf
        try:
            generated_content = self.client.generate_text(
                prompt=user_prompt, system_prompt=system_prompt, max_tokens=1500, temperature=0.7
            )
        except LLMClientError as e:
            raise LessonPlanGenerationError(_("LLM error: {error}").format(error=str(e))) from e

        # Erstelle oder aktualisiere LessonPlan
        student = lesson.contract.student
        subject = extract_subject_from_student(student)

        lesson_plan, created = LessonPlan.objects.update_or_create(
            lesson=lesson,
            defaults={
                "student": student,
                "topic": _("Lesson plan for {date}").format(date=lesson.date),
                "subject": subject,
                "content": generated_content,
                "grade_level": student.grade or "",
                "duration_minutes": lesson.duration_minutes,
                "llm_model": settings.LLM_MODEL_NAME,
            },
        )

        return lesson_plan
