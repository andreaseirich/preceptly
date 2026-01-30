"""
Views for AI functions (lesson plan generation).
"""

from apps.ai.services import LessonPlanGenerationError, LessonPlanService
from apps.core.utils import is_premium_user
from apps.lessons.models import Session
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST


@login_required
@require_POST
def generate_lesson_plan(request, lesson_id):
    """
    Generates an AI lesson plan for a session.
    Only available for premium users.
    """
    session = get_object_or_404(Session, pk=lesson_id, contract__student__user=request.user)

    # Premium-Check
    if not is_premium_user(request.user):
        messages.error(request, _("This function is only available for premium users."))
        # Redirect to lesson plan view if 'next' parameter is provided, otherwise to lesson detail
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("lessons:detail", pk=lesson_id)

    # Generate lesson plan
    try:
        service = LessonPlanService()
        lesson_plan = service.generate_lesson_plan(session)
        messages.success(
            request,
            _("Lesson plan successfully generated! Model: {model}").format(
                model=lesson_plan.llm_model or "N/A"
            ),
        )
    except LessonPlanGenerationError as e:
        messages.error(
            request, _("The lesson plan could not be generated: {error}").format(error=str(e))
        )
        # Log the error for debugging
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Lesson plan generation failed: {str(e)}", exc_info=True)
    except Exception as e:
        # Log unexpected errors with full traceback
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error during lesson plan generation: {str(e)}", exc_info=True)
        messages.error(
            request,
            _(
                "An unexpected error occurred: {error}. Please check the logs or try again later."
            ).format(error=str(e)),
        )

    # Redirect to lesson plan view if 'next' parameter is provided, otherwise to session detail
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("lessons:detail", pk=lesson_id)
