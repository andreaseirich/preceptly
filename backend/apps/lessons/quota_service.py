"""
Service für Kontingent-Prüfung basierend auf ContractMonthlyPlan.
"""

from datetime import date
from typing import Optional

from apps.contracts.models import ContractMonthlyPlan
from apps.lessons.models import Lesson
from django.utils.translation import gettext as _


class ContractQuotaService:
    """Service für Prüfung von Vertragskontingenten."""

    @staticmethod
    def check_quota_conflict(lesson: Lesson, exclude_self: bool = True) -> Optional[dict]:
        """
        Prüft, ob eine Lesson das Vertragskontingent überschreitet.

        Regel:
        - Man darf im Verlauf eines Vertragszeitraums nicht "vorarbeiten".
        - Für jeden Monat M gilt:
            Summe der tatsächlich gehalten/geplanten Lessons von Vertragsbeginn bis Ende Monat M
            darf die Summe der geplanten Einheiten (ContractMonthlyPlan) von Vertragsbeginn bis Monat M NICHT überschreiten.
        - Nachholen ist erlaubt (wenn in früheren Monaten weniger als geplant stattgefunden hat).

        Args:
            lesson: Lesson-Objekt
            exclude_self: Wenn True, wird die Lesson selbst von der Prüfung ausgeschlossen

        Returns:
            Dict mit 'type', 'message', 'planned_total', 'actual_total' wenn Konflikt,
            sonst None
        """
        contract = lesson.contract

        # If has_monthly_planning_limit is disabled, there is no quota check
        if not contract.has_monthly_planning_limit:
            return None

        # Determine the month of the lesson
        lesson_year = lesson.date.year
        lesson_month = lesson.date.month

        # Get all ContractMonthlyPlan entries from contract start to including lesson month
        # Sort by year and month
        monthly_plans = ContractMonthlyPlan.objects.filter(
            contract=contract, year__lte=lesson_year
        ).order_by("year", "month")

        # Filter: Only plans up to and including the lesson month
        relevant_plans = []
        for plan in monthly_plans:
            if plan.year < lesson_year or (plan.year == lesson_year and plan.month <= lesson_month):
                relevant_plans.append(plan)

        # Calculate planned total units up to and including this month
        planned_total = sum(plan.planned_units for plan in relevant_plans)

        # Calculate actual lessons from contract start to end of this month
        # Use the end of the lesson month
        from calendar import monthrange

        last_day_of_month = monthrange(lesson_year, lesson_month)[1]
        month_end = date(lesson_year, lesson_month, last_day_of_month)

        # Get all lessons of this contract with date <= month end
        # Status: PLANNED, TAUGHT, PAID (no CANCELLED)
        lessons_query = Lesson.objects.filter(
            contract=contract, date__lte=month_end, status__in=["planned", "taught", "paid"]
        )

        if exclude_self and lesson.pk:
            lessons_query = lessons_query.exclude(pk=lesson.pk)

        actual_lessons = lessons_query.count()

        # Check: actual_lessons + 1 (the new lesson) > planned_total
        if actual_lessons + 1 > planned_total:
            return {
                "type": "quota",
                "message": _(
                    "Contract quota exceeded: "
                    "By the end of {month:02d}.{year}, {planned} units are planned, "
                    "but {actual} hours are present/planned."
                ).format(
                    month=lesson_month,
                    year=lesson_year,
                    planned=planned_total,
                    actual=actual_lessons + 1,
                ),
                "planned_total": planned_total,
                "actual_total": actual_lessons + 1,
                "month": lesson_month,
                "year": lesson_year,
            }

        return None

    @staticmethod
    def has_quota_conflict(lesson: Lesson, exclude_self: bool = True) -> bool:
        """
        Prüft, ob eine Lesson einen Quota-Konflikt hat (vereinfachte Version).

        Args:
            lesson: Lesson-Objekt
            exclude_self: Wenn True, wird die Lesson selbst ausgeschlossen

        Returns:
            True wenn Quota-Konflikt vorhanden, sonst False
        """
        return ContractQuotaService.check_quota_conflict(lesson, exclude_self) is not None
