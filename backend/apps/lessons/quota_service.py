"""
Service für Kontingent-Prüfung basierend auf ContractMonthlyPlan.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date
from typing import Optional

from django.utils.translation import gettext as _

from apps.contracts.models import ContractMonthlyPlan
from apps.lessons.models import Lesson

COUNTED_STATUSES = ["planned", "taught", "paid"]


def _month_end(day: date) -> date:
    return date(day.year, day.month, monthrange(day.year, day.month)[1])


def _plans_until(lesson: Lesson, plans) -> list:
    """Monatspläne von Vertragsbeginn bis einschließlich zum Monat der Stunde."""
    y, m = lesson.date.year, lesson.date.month
    return [p for p in plans if p.year < y or (p.year == y and p.month <= m)]


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

        plans = list(
            ContractMonthlyPlan.objects.filter(contract=contract, year__lte=lesson.date.year)
        )
        # If no monthly plans exist for this period, there is no quota restriction
        if not _plans_until(lesson, plans):
            return None

        lessons_query = Lesson.objects.filter(
            contract=contract, date__lte=_month_end(lesson.date), status__in=COUNTED_STATUSES
        )
        if exclude_self and lesson.pk:
            lessons_query = lessons_query.exclude(pk=lesson.pk)
        return ContractQuotaService.quota_conflict_from(lesson, plans, lessons_query.count())

    @staticmethod
    def quota_conflict_from(lesson: Lesson, plans, other_lessons: int) -> Optional[dict]:
        """Die Kontingentregel als reine Rechnung, ohne Datenbank.

        plans: Monatspläne des Vertrags (beliebige Reihenfolge, auch spätere Monate),
        other_lessons: Stunden des Vertrags bis Monatsende, ohne diese Stunde
        (bzw. mit ihr, wenn exclude_self=False - wie bisher).
        """
        relevant_plans = _plans_until(lesson, plans)
        if not relevant_plans:
            return None
        planned_total = sum(plan.planned_units for plan in relevant_plans)
        lesson_year, lesson_month = lesson.date.year, lesson.date.month

        # Check: other lessons + 1 (this one) > planned_total
        if other_lessons + 1 > planned_total:
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
                    actual=other_lessons + 1,
                ),
                "planned_total": planned_total,
                "actual_total": other_lessons + 1,
                "month": lesson_month,
                "year": lesson_year,
            }

        return None

    @staticmethod
    def preload(lessons) -> dict:
        """Monatspläne und gezählte Stunden aller Verträge mit Kontingent - zwei
        Abfragen für beliebig viele Stunden (für quota_conflict_from_preloaded)."""
        limited = [lsn for lsn in lessons if lsn.contract.has_monthly_planning_limit]
        if not limited:
            return {"plans": {}, "lessons": {}}
        contract_ids = {lsn.contract_id for lsn in limited}
        plans = defaultdict(list)
        for plan in ContractMonthlyPlan.objects.filter(contract_id__in=contract_ids):
            plans[plan.contract_id].append(plan)
        counted = defaultdict(list)
        for contract_id, day, pk in Lesson.objects.filter(
            contract_id__in=contract_ids,
            date__lte=max(_month_end(lsn.date) for lsn in limited),
            status__in=COUNTED_STATUSES,
        ).values_list("contract_id", "date", "pk"):
            counted[contract_id].append((day, pk))
        return {"plans": plans, "lessons": counted}

    @staticmethod
    def quota_conflict_from_preloaded(
        lesson: Lesson, preloaded: dict, exclude_self: bool = True
    ) -> Optional[dict]:
        """check_quota_conflict mit den Daten aus preload()."""
        if not lesson.contract.has_monthly_planning_limit:
            return None
        month_end = _month_end(lesson.date)
        others = sum(
            1
            for day, pk in preloaded["lessons"].get(lesson.contract_id, [])
            if day <= month_end and not (exclude_self and lesson.pk and pk == lesson.pk)
        )
        return ContractQuotaService.quota_conflict_from(
            lesson, preloaded["plans"].get(lesson.contract_id, []), others
        )

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
