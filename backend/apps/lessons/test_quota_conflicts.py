"""
Tests für Kontingent-Konflikte (ContractQuotaService).
"""

from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.lessons.models import Lesson
from apps.lessons.quota_service import ContractQuotaService
from apps.students.models import Student


class ContractQuotaServiceTest(TestCase):
    """Tests für ContractQuotaService."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Setzt Testdaten auf."""
        self.student = Student.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
        )

        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=30.00,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 9, 30),
            is_active=True,
        )

        # Erstelle monatliche Pläne
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=8, planned_units=3
        )
        ContractMonthlyPlan.objects.create(
            contract=self.contract, year=2025, month=9, planned_units=5
        )

    def test_scenario_1_quota_exceeded(self):
        """
        Szenario 1: Quota überschritten.
        - August: 3 Einheiten geplant, 3 Stunden → ok
        - September: 5 Einheiten geplant, 5 Stunden → ok
        - weitere Lesson im September → Konflikt
        """
        # Erstelle 3 Lessons im August
        for i in range(3):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 8, 5 + i),
                start_time=time(14, 0),
                duration_minutes=60,
                status="planned",
            )

        # Erstelle 5 Lessons im September
        for i in range(5):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 9, 5 + i),
                start_time=time(14, 0),
                duration_minutes=60,
                status="planned",
            )

        # Versuche eine weitere Lesson im September zu erstellen
        new_lesson = Lesson(
            contract=self.contract,
            date=date(2025, 9, 20),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe Konflikt
        conflict = ContractQuotaService.check_quota_conflict(new_lesson, exclude_self=True)

        self.assertIsNotNone(conflict)
        self.assertEqual(conflict["type"], "quota")
        self.assertEqual(conflict["planned_total"], 8)  # 3 + 5
        self.assertEqual(conflict["actual_total"], 9)  # 3 + 5 + 1

    def test_scenario_2_catch_up_allowed(self):
        """
        Szenario 2: Nachholen erlaubt.
        - August: nur 1 Stunde, geplant 3
        - September: 5 Stunden, geplant 5
        - Summe bis Ende September: 6 tatsächliche Stunden, 8 geplant → kein Konflikt
        """
        # Erstelle nur 1 Lesson im August
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Erstelle 5 Lessons im September
        for i in range(5):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 9, 5 + i),
                start_time=time(14, 0),
                duration_minutes=60,
                status="planned",
            )

        # Versuche eine weitere Lesson im September zu erstellen
        new_lesson = Lesson(
            contract=self.contract,
            date=date(2025, 9, 20),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe Konflikt
        conflict = ContractQuotaService.check_quota_conflict(new_lesson, exclude_self=True)

        # Sollte kein Konflikt sein: 1 + 5 + 1 = 7 <= 8
        self.assertIsNone(conflict)

    def test_scenario_3_no_advance_work(self):
        """
        Szenario 3: Vorarbeiten nicht erlaubt.
        - Versuch, vor September bereits 8+ Stunden zu planen (z. B. alles im August)
        - Konflikt ab der 4. August-Stunde
        """
        # Erstelle 3 Lessons im August (ok)
        for i in range(3):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 8, 5 + i),
                start_time=time(14, 0),
                duration_minutes=60,
                status="planned",
            )

        # Versuche eine 4. Lesson im August zu erstellen
        new_lesson = Lesson(
            contract=self.contract,
            date=date(2025, 8, 20),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe Konflikt
        conflict = ContractQuotaService.check_quota_conflict(new_lesson, exclude_self=True)

        # Sollte Konflikt sein: 4 > 3 (geplant für August)
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict["type"], "quota")
        self.assertEqual(conflict["planned_total"], 3)  # Nur August
        self.assertEqual(conflict["actual_total"], 4)  # 3 + 1

    def test_cancelled_lessons_not_counted(self):
        """Test: CANCELLED Lessons werden nicht gezählt."""
        # Erstelle 3 Lessons im August (ok)
        for i in range(3):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2025, 8, 5 + i),
                start_time=time(14, 0),
                duration_minutes=60,
                status="planned",
            )

        # Erstelle eine stornierte Lesson
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 10),
            start_time=time(14, 0),
            duration_minutes=60,
            status="cancelled",  # Storniert
        )

        # Versuche eine weitere Lesson im August zu erstellen
        new_lesson = Lesson(
            contract=self.contract,
            date=date(2025, 8, 20),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe Konflikt
        conflict = ContractQuotaService.check_quota_conflict(new_lesson, exclude_self=True)

        # Sollte Konflikt sein: 3 + 1 = 4 > 3 (stornierte wird nicht gezählt)
        self.assertIsNotNone(conflict)

    def test_taught_and_paid_lessons_counted(self):
        """Test: TAUGHT und PAID Lessons werden gezählt."""
        # Erstelle 2 Lessons im August mit verschiedenen Status
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 8, 6),
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )

        # Versuche eine 3. Lesson im August zu erstellen
        new_lesson = Lesson(
            contract=self.contract,
            date=date(2025, 8, 7),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe Konflikt
        conflict = ContractQuotaService.check_quota_conflict(new_lesson, exclude_self=True)

        # Sollte kein Konflikt sein: 2 + 1 = 3 <= 3
        self.assertIsNone(conflict)
