"""
Selector-Layer für Einnahmenauswertungen.
Abgeleitete Monats-/Jahresauswertungen ohne eigenes Model.
"""

from datetime import date
from decimal import Decimal

from apps.billing.models import InvoiceItem
from apps.contracts.models import ContractMonthlyPlan
from apps.lessons.models import Lesson
from django.db.models import Q


class IncomeSelector:
    """
    Selector für Einnahmenberechnungen und -auswertungen.

    Verwendet die gleiche Berechnungslogik wie das Abrechnungssystem:
    - units = lesson_duration_minutes / contract_unit_duration_minutes
    - amount = units * hourly_rate

    Für Lessons, die in Rechnungen enthalten sind, werden die Beträge
    aus den InvoiceItems genommen (Single Source of Truth).
    """

    @staticmethod
    def _calculate_lesson_amount(lesson: Lesson) -> Decimal:
        """
        Berechnet den Betrag für eine Lesson mit der gleichen Logik wie InvoiceService.

        Args:
            lesson: Lesson-Instanz

        Returns:
            Betrag als Decimal
        """
        contract = lesson.contract
        unit_duration = Decimal(str(contract.unit_duration_minutes))
        lesson_duration = Decimal(str(lesson.duration_minutes))
        units = lesson_duration / unit_duration
        rate_per_unit = contract.hourly_rate
        amount = units * rate_per_unit
        return amount

    @staticmethod
    def _get_lesson_amount(lesson: Lesson) -> Decimal:
        """
        Gibt den Betrag für eine Lesson zurück.

        Wenn die Lesson in einer Rechnung ist, wird der Betrag aus dem InvoiceItem genommen.
        Sonst wird der Betrag mit der gleichen Logik wie InvoiceService berechnet.

        Args:
            lesson: Lesson-Instanz

        Returns:
            Betrag als Decimal
        """
        # Check if lesson is in an invoice
        invoice_item = InvoiceItem.objects.filter(lesson=lesson).first()
        if invoice_item:
            # Use amount from InvoiceItem (Single Source of Truth)
            return invoice_item.amount
        else:
            # Calculate amount with same logic as InvoiceService
            return IncomeSelector._calculate_lesson_amount(lesson)

    @staticmethod
    def get_monthly_income(year: int, month: int, status: str = "paid") -> dict:
        """
        Berechnet die Einnahmen für einen bestimmten Monat.

        Args:
            year: Jahr
            month: Monat (1-12)
            status: Status der Lessons ('paid' = ausgezahlt)

        Returns:
            Dict mit Einnahmen-Details
        """
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        lessons = Lesson.objects.filter(
            date__gte=start_date, date__lt=end_date, status=status
        ).select_related("contract")

        total_income = Decimal("0.00")
        lesson_count = 0
        contract_details = {}

        for lesson in lessons:
            # Use central calculation method (same logic as InvoiceService)
            lesson_income = IncomeSelector._get_lesson_amount(lesson)
            total_income += lesson_income
            lesson_count += 1

            contract_id = lesson.contract.id
            if contract_id not in contract_details:
                contract_details[contract_id] = {
                    "contract": lesson.contract,
                    "lessons": 0,
                    "income": Decimal("0.00"),
                }
            contract_details[contract_id]["lessons"] += 1
            contract_details[contract_id]["income"] += lesson_income

        return {
            "year": year,
            "month": month,
            "total_income": total_income,
            "lesson_count": lesson_count,
            "contract_details": list(contract_details.values()),
        }

    @staticmethod
    def get_monthly_planned_vs_actual(year: int, month: int) -> dict:
        """
        Vergleicht geplante vs. tatsächliche Einheiten und Einnahmen für einen Monat.

        Args:
            year: Jahr
            month: Monat (1-12)

        Returns:
            Dict mit planned_units, planned_amount, actual_units, actual_amount
        """
        # Geplante Einheiten aus ContractMonthlyPlan
        monthly_plans = ContractMonthlyPlan.objects.filter(year=year, month=month)
        planned_units = sum(plan.planned_units for plan in monthly_plans)
        planned_amount = Decimal("0.00")

        for plan in monthly_plans:
            # Planned income uses rate per unit (unit already represents one block)
            hourly_rate = plan.contract.hourly_rate
            planned_amount += hourly_rate * Decimal(plan.planned_units)

        # Actual units from lessons
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        lessons = Lesson.objects.filter(date__gte=start_date, date__lt=end_date).select_related(
            "contract"
        )

        actual_units = lessons.count()
        actual_amount = Decimal("0.00")

        for lesson in lessons:
            # Use central calculation method (same logic as InvoiceService)
            actual_amount += IncomeSelector._calculate_lesson_amount(lesson)

        return {
            "year": year,
            "month": month,
            "planned_units": planned_units,
            "planned_amount": planned_amount,
            "actual_units": actual_units,
            "actual_amount": actual_amount,
            "difference_units": actual_units - planned_units,
            "difference_amount": actual_amount - planned_amount,
        }

    @staticmethod
    def get_yearly_income(year: int, status: str = "paid") -> dict:
        """
        Berechnet die Einnahmen für ein ganzes Jahr.

        Args:
            year: Jahr
            status: Status der Lessons ('paid' = ausgezahlt)

        Returns:
            Dict mit Einnahmen-Details pro Monat und Gesamt
        """
        monthly_incomes = []
        total_income = Decimal("0.00")
        total_lessons = 0

        for month in range(1, 13):
            monthly_data = IncomeSelector.get_monthly_income(year, month, status)
            monthly_incomes.append(monthly_data)
            total_income += monthly_data["total_income"]
            total_lessons += monthly_data["lesson_count"]

        return {
            "year": year,
            "total_income": total_income,
            "total_lessons": total_lessons,
            "monthly_breakdown": monthly_incomes,
        }

    @staticmethod
    def get_income_by_status(year: int = None, month: int = None) -> dict:
        """
        Gruppiert Einnahmen nach Status.

        Args:
            year: Optional - Jahr
            month: Optional - Monat

        Returns:
            Dict mit Einnahmen nach Status
        """
        query = Q()
        if year and month:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            query &= Q(date__gte=start_date, date__lt=end_date)
        elif year:
            query &= Q(date__year=year)

        lessons = Lesson.objects.filter(query).select_related("contract")

        status_breakdown = {}
        for status_code, status_name in Lesson.STATUS_CHOICES:
            status_lessons = lessons.filter(status=status_code)
            total_income = Decimal("0.00")
            lesson_count = status_lessons.count()

            for lesson in status_lessons:
                # Use central calculation method (same logic as InvoiceService)
                total_income += IncomeSelector._get_lesson_amount(lesson)

            status_breakdown[status_code] = {
                "name": status_name,
                "income": total_income,
                "lesson_count": lesson_count,
            }

        return status_breakdown

    @staticmethod
    def get_billing_status(year: int = None, month: int = None) -> dict:
        """
        Gibt Informationen über abgerechnete vs. nicht abgerechnete Lessons zurück.

        Abgerechnet = Lessons mit InvoiceItem (unabhängig vom Status).
        Nicht abgerechnet = Lessons mit Status TAUGHT ohne InvoiceItem.

        Args:
            year: Optional - Jahr
            month: Optional - Monat

        Returns:
            Dict mit 'invoiced' und 'not_invoiced' Informationen
        """
        # Base query for period
        query = Q()
        if year and month:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            query &= Q(date__gte=start_date, date__lt=end_date)
        elif year:
            query &= Q(date__year=year)

        # Lessons with InvoiceItem (invoiced) - regardless of status
        invoiced_lesson_ids = InvoiceItem.objects.filter(lesson__isnull=False).values_list(
            "lesson_id", flat=True
        )
        invoiced_lessons = Lesson.objects.filter(
            query & Q(id__in=invoiced_lesson_ids)
        ).select_related("contract")

        # Lessons without InvoiceItem with status TAUGHT (not invoiced, but taught)
        not_invoiced_lessons = (
            Lesson.objects.filter(query & Q(status="taught"))
            .exclude(id__in=invoiced_lesson_ids)
            .select_related("contract")
        )

        # Calculate income
        # For invoiced lessons: amounts from InvoiceItems (Single Source of Truth)
        invoiced_income = Decimal("0.00")
        for lesson in invoiced_lessons:
            invoice_item = InvoiceItem.objects.filter(lesson=lesson).first()
            if invoice_item:
                invoiced_income += invoice_item.amount
            else:
                # Fallback: calculate with same logic
                invoiced_income += IncomeSelector._calculate_lesson_amount(lesson)

        # For not invoiced lessons: calculate with same logic as InvoiceService
        not_invoiced_income = Decimal("0.00")
        for lesson in not_invoiced_lessons:
            not_invoiced_income += IncomeSelector._calculate_lesson_amount(lesson)

        return {
            "invoiced": {
                "lesson_count": invoiced_lessons.count(),
                "income": invoiced_income,
                "lessons": invoiced_lessons,
            },
            "not_invoiced": {
                "lesson_count": not_invoiced_lessons.count(),
                "income": not_invoiced_income,
                "lessons": not_invoiced_lessons,
            },
        }
