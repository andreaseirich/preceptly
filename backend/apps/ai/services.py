"""
High-level service for lesson plan generation.
"""

from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from apps.ai.client import LLMClient, LLMClientError, LLMServiceUnavailableError
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
            user: User performing the request (REQUIRED – no default)

        Returns:
            LessonPlan object

        Raises:
            PermissionDenied: If user is None or does not own the session
            LessonPlanGenerationError: On generation errors
        """
        # [HIGH] user ist PFLICHT – kein opt-in Ownership-Check
        if user is None:
            raise PermissionDenied("User is required for lesson plan generation.")
        if session.contract.user_id != user.id:
            raise PermissionDenied("Session does not belong to user.")

        # [MEDIUM] Rate-Limiting: max. 10 Generierungen pro User pro Stunde
        rate_key = f"llm_gen_rate:{user.id}"
        current_count = cache.get(rate_key, 0)
        if current_count >= 10:
            raise LessonPlanGenerationError(_("Rate limit reached. Please try again later."))
        cache.set(rate_key, current_count + 1, 3600)

        # Gather context and apply PII protection
        raw_context = self.gather_context(session)
        safe_context = sanitize_context(raw_context)

        # Build prompt
        system_prompt, user_prompt = build_lesson_plan_prompt(session, safe_context)

        # [MEDIUM] Lock entkoppeln: nur Existenz-Check + Placeholder in atomarer Transaktion,
        # LLM-Call AUSSERHALB des Locks (verhindert DoS durch lange DB-Lock-Haltedauer)
        with transaction.atomic():
            existing = LessonPlan.objects.select_for_update().filter(lesson=session).first()
            if existing is not None:
                # Bereits ein aktueller Plan vorhanden – direkt zurückgeben
                return existing

            # Platzhalter-Row anlegen, damit parallele Requests denselben Plan nicht
            # doppelt generieren (unique constraint auf lesson greift)
            student = session.contract
            raw_subject = extract_subject_from_student(student)
            subject = strip_injection_patterns(raw_subject)[:100]

            placeholder = LessonPlan.objects.create(
                lesson=session,
                contract=student,
                topic=_("Lesson plan for {date}").format(date=session.date),
                subject=subject,
                content="",
                grade_level=student.grade or "",
                duration_minutes=session.duration_minutes,
                llm_model=settings.LLM_MODEL_NAME,
            )
        # Transaktion beendet → Lock freigegeben

        # LLM-Call außerhalb des Locks (kann bis zu 120 s dauern)
        try:
            generated_content = self.client.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=1500,
                temperature=0.7,
            )
        except LLMServiceUnavailableError as e:
            # Placeholder aufräumen damit ein erneuter Versuch möglich ist
            placeholder.delete()
            raise LessonPlanGenerationError(
                _("The AI is temporarily unreachable. Please try again in a few minutes.")
            ) from e
        except LLMClientError as e:
            # Placeholder aufräumen damit ein erneuter Versuch möglich ist
            placeholder.delete()
            raise LessonPlanGenerationError(
                _("The lesson plan could not be generated. Please try again.")
            ) from e

        # [MEDIUM] Output-Safety: Länge begrenzen + HTML-Sonderzeichen neutralisieren
        # (verhindert Stored-XSS falls der Content später gerendert wird)
        generated_content = generated_content[:20000]
        generated_content = escape(generated_content)

        # Placeholder mit realem Inhalt aktualisieren
        placeholder.content = generated_content
        placeholder.save(update_fields=["content"])

        return placeholder
