"""
Views for AI functions (lesson plan generation).
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.ai.services import LessonPlanGenerationError, LessonPlanService
from apps.core.feature_flags import Feature, user_has_feature
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Session

logger = logging.getLogger(__name__)


@login_required
@require_POST
@ratelimit(key="user", rate="20/h", method="POST", block=True)
def generate_lesson_plan(request, lesson_id):
    """
    Generates an AI lesson plan for a session.
    Only available for premium users.
    """
    session = get_object_or_404(Session, pk=lesson_id, contract__user=request.user)

    # Premium-Check
    if not user_has_feature(request.user, Feature.FEATURE_AI_LESSON_PLANS):
        messages.error(request, _("This function is only available for premium users."))
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("lessons:detail", pk=lesson_id)

    # Täglicher Quota-Cap (M8): Kosten-DoS verhindern
    MAX_DAILY_GENERATIONS = 20
    today = timezone.localdate()
    daily_count = LessonPlan.objects.filter(
        contract__user=request.user,
        created_at__date=today,
    ).count()
    if daily_count >= MAX_DAILY_GENERATIONS:
        messages.error(request, _("Daily limit reached. Try again tomorrow."))
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("lessons:detail", pk=lesson_id)

    # Generate lesson plan
    try:
        service = LessonPlanService()
        lesson_plan = service.generate_lesson_plan(session, user=request.user)
        messages.success(
            request,
            _("Lesson plan successfully generated! Model: {model}").format(
                model=lesson_plan.llm_model or "N/A"
            ),
        )
    except LessonPlanGenerationError as e:
        messages.error(request, _("Ein Fehler ist aufgetreten. Bitte versuche es erneut."))
        logger.error(f"Lesson plan generation failed: {str(e)}", exc_info=True)
    except Exception as e:
        messages.error(request, _("Ein Fehler ist aufgetreten. Bitte versuche es erneut."))
        logger.error(f"Unexpected error during lesson plan generation: {str(e)}", exc_info=True)

    # Redirect to lesson plan view if 'next' parameter is provided, otherwise to session detail
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("lessons:detail", pk=lesson_id)
