"""
Tests für ContractMonthlyPlan und monatliche Planung.
"""

from datetime import date
from decimal import Decimal

from apps.contracts.formsets import generate_monthly_plans_for_contract, iter_contract_months
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.db import IntegrityError
from django.test import TestCase
from django.contrib.auth.models import User


class ContractMonthlyPlanTest(TestCase):
    """Tests für ContractMonthlyPlan Model."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Max", last_name="Mustermann", email="max@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
            is_active=True,
        )

    def test_create_monthly_plan(self):
        """Test: Erstellen eines monatlichen Plans."""
        plan = ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=1, planned_units=8
        )
        self.assertEqual(plan.contract, self.contract)
        self.assertEqual(plan.year, 2025)
        self.assertEqual(plan.month, 1)
        self.assertEqual(plan.planned_units, 8)

    def test_unique_together_constraint(self):
        """Test: unique_together Constraint verhindert doppelte Einträge."""
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=1, planned_units=8
        )
        # Zweiter Eintrag für denselben Monat sollte fehlschlagen
        with self.assertRaises(IntegrityError):
            ContractMonthlyPlan.objects.create(
                contract=self.contract, year=2025, month=1, planned_units=10
            )


class GenerateMonthlyPlansTest(TestCase):
    """Tests für generate_monthly_plans_for_contract."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Anna", last_name="Schmidt", email="anna@example.com"
        )

    def test_generate_plans_for_date_range(self):
        """Test: Generierung von Plänen für einen Zeitraum."""
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            start_date=date(2025, 1, 15),
            end_date=date(2025, 3, 15),
            is_active=True,
        )

        plans = generate_monthly_plans_for_contract(contract)

        # Sollte Pläne für Januar, Februar, März erstellen
        self.assertEqual(len(plans), 3)
        self.assertEqual(plans[0].year, 2025)
        self.assertEqual(plans[0].month, 1)
        self.assertEqual(plans[1].month, 2)
        self.assertEqual(plans[2].month, 3)

    def test_generate_plans_unlimited_contract(self):
        """Test: Generierung für unbefristeten Vertrag (1 Jahr voraus)."""
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            start_date=date(2025, 1, 1),
            end_date=None,
            is_active=True,
        )

        plans = generate_monthly_plans_for_contract(contract)

        # Sollte mindestens 12 Monate generieren
        self.assertGreaterEqual(len(plans), 12)

    def test_generate_plans_preserves_existing(self):
        """Test: Vorhandene Pläne werden nicht überschrieben."""
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 28),
            is_active=True,
        )

        # Erstelle manuell einen Plan
        existing_plan = ContractMonthlyPlan.objects.create(
            contract=contract, year=2025, month=1, planned_units=10
        )

        # Generiere Pläne erneut
        generate_monthly_plans_for_contract(contract)

        # Existierender Plan sollte erhalten bleiben
        existing_plan.refresh_from_db()
        self.assertEqual(existing_plan.planned_units, 10)


class IncomeSelectorPlannedVsActualTest(TestCase):
    """Tests für IncomeSelector mit geplanten vs. tatsächlichen Einheiten."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Tom", last_name="Weber", email="tom@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("28.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_planned_vs_actual_month_with_plan(self):
        """Test: Vergleich geplant vs. tatsächlich mit Plan-Einträgen."""
        # Erstelle Plan-Einträge
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=1, planned_units=8
        )
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=2, planned_units=4
        )

        # Erstelle tatsächliche Lessons
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 10),
            start_time="14:00",
            duration_minutes=60,
            status="paid",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 20),
            start_time="15:00",
            duration_minutes=60,
            status="paid",
        )
        # Februar: mehr tatsächliche als geplante
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 2, 5),
            start_time="14:00",
            duration_minutes=60,
            status="paid",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 2, 12),
            start_time="15:00",
            duration_minutes=60,
            status="paid",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 2, 19),
            start_time="16:00",
            duration_minutes=60,
            status="paid",
        )

        # Test Januar: geplant 8, tatsächlich 2
        result_jan = IncomeSelector.get_monthly_planned_vs_actual(2025, 1)
        self.assertEqual(result_jan["planned_units"], 8)
        self.assertEqual(result_jan["actual_units"], 2)
        self.assertEqual(result_jan["difference_units"], -6)

        # Test Februar: geplant 4, tatsächlich 3
        result_feb = IncomeSelector.get_monthly_planned_vs_actual(2025, 2)
        self.assertEqual(result_feb["planned_units"], 4)
        self.assertEqual(result_feb["actual_units"], 3)
        self.assertEqual(result_feb["difference_units"], -1)

    def test_planned_vs_actual_month_without_plan(self):
        """Test: Monat ohne Plan-Einträge."""
        # Keine Plan-Einträge für März
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 10),
            start_time="14:00",
            duration_minutes=60,
            status="paid",
        )

        result = IncomeSelector.get_monthly_planned_vs_actual(2025, 3)
        self.assertEqual(result["planned_units"], 0)
        self.assertEqual(result["actual_units"], 1)
        self.assertEqual(result["difference_units"], 1)
        self.assertEqual(result["planned_amount"], Decimal("0.00"))
        self.assertGreater(result["actual_amount"], Decimal("0.00"))

    def test_planned_amount_calculation(self):
        """Test: Berechnung des geplanten Betrags."""
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=1, planned_units=10
        )

        result = IncomeSelector.get_monthly_planned_vs_actual(2025, 1)
        # 10 Einheiten * 28€ * 1 Stunde = 280€
        expected = Decimal("28.00") * Decimal("10")
        self.assertEqual(result["planned_amount"], expected)


class MonthlyPlanningDateRangeTest(TestCase):
    """Tests für monatliche Planung unabhängig vom aktuellen Datum."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Lisa", last_name="Müller", email="lisa@example.com"
        )

    def test_future_contract_all_months(self):
        """Test: Vertrag mit Zeitraum in der Zukunft - alle Monate bis Vertragsende."""
        # Vertrag für nächstes Jahr (2026)
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            is_active=True,
        )

        plans = generate_monthly_plans_for_contract(contract)

        # Sollte alle 6 Monate (Januar bis Juni 2026) abdecken
        self.assertEqual(len(plans), 6)
        self.assertEqual(plans[0].year, 2026)
        self.assertEqual(plans[0].month, 1)
        self.assertEqual(plans[-1].year, 2026)
        self.assertEqual(plans[-1].month, 6)

        # Prüfe, dass alle Monate vorhanden sind
        months = [(p.year, p.month) for p in plans]
        expected_months = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6)]
        self.assertEqual(set(months), set(expected_months))

    def test_past_to_future_contract_all_months(self):
        """Test: Vertrag, der in der Vergangenheit begonnen hat und in der Zukunft endet."""
        # Vertrag von 2024 bis 2026
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            start_date=date(2024, 10, 1),
            end_date=date(2026, 3, 31),
            is_active=True,
        )

        plans = generate_monthly_plans_for_contract(contract)

        # Sollte alle Monate von Oktober 2024 bis März 2026 abdecken
        # Das sind: Okt, Nov, Dez 2024 (3) + 12 Monate 2025 (12) + Jan, Feb, Mär 2026 (3) = 18 Monate
        self.assertEqual(len(plans), 18)
        self.assertEqual(plans[0].year, 2024)
        self.assertEqual(plans[0].month, 10)
        self.assertEqual(plans[-1].year, 2026)
        self.assertEqual(plans[-1].month, 3)

    def test_past_contract_all_months(self):
        """Test: Vertrag, der komplett in der Vergangenheit liegt."""
        # Vertrag von 2023
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("20.00"),
            start_date=date(2023, 5, 1),
            end_date=date(2023, 8, 31),
            is_active=True,
        )

        plans = generate_monthly_plans_for_contract(contract)

        # Sollte alle 4 Monate (Mai bis August 2023) abdecken
        self.assertEqual(len(plans), 4)
        self.assertEqual(plans[0].year, 2023)
        self.assertEqual(plans[0].month, 5)
        self.assertEqual(plans[-1].year, 2023)
        self.assertEqual(plans[-1].month, 8)

        # Prüfe, dass alle Monate vorhanden sind
        months = [(p.year, p.month) for p in plans]
        expected_months = [(2023, 5), (2023, 6), (2023, 7), (2023, 8)]
        self.assertEqual(set(months), set(expected_months))

    def test_iter_contract_months_function(self):
        """Test: iter_contract_months Hilfsfunktion."""
        # Test mit festem Zeitraum
        months = iter_contract_months(date(2025, 1, 15), date(2025, 3, 20))
        self.assertEqual(len(months), 3)
        self.assertEqual(months[0], (2025, 1))
        self.assertEqual(months[1], (2025, 2))
        self.assertEqual(months[2], (2025, 3))

        # Test mit unbefristetem Vertrag (sollte 5 Jahre generieren)
        months_unlimited = iter_contract_months(date(2025, 1, 1), None)
        self.assertEqual(len(months_unlimited), 60)  # 5 Jahre * 12 Monate
        self.assertEqual(months_unlimited[0], (2025, 1))
        self.assertEqual(months_unlimited[-1], (2029, 12))

    def test_future_contract_formset_editable(self):
        """Test: Formset für zukünftigen Vertrag zeigt alle Monate als editierbar."""
        contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
        )

        # Generiere Pläne
        generate_monthly_plans_for_contract(contract)

        # Prüfe, dass alle 12 Monate vorhanden sind
        plans = ContractMonthlyPlan.objects.filter(contract=contract).order_by("year", "month")
        self.assertEqual(plans.count(), 12)

        # Prüfe, dass alle Monate von Januar bis Dezember abgedeckt sind
        months = [(p.year, p.month) for p in plans]
        expected_months = [(2027, m) for m in range(1, 13)]
        self.assertEqual(set(months), set(expected_months))
