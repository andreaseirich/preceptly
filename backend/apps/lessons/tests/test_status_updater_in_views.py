"""
Tests für automatische Status-Aktualisierung in Views.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone


class StatusUpdaterInViewsTest(TestCase):
    """Tests, dass Views automatisch Status aktualisieren."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client.login(username="testuser", password="testpass123")

        self.student = Student.objects.create(
            user=self.user, first_name="Max", last_name="Mustermann", email="max@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_dashboard_view_updates_past_lessons(self):
        """Test: Dashboard-View aktualisiert vergangene Lessons automatisch."""
        # Erstelle eine vergangene Lesson mit Status PLANNED
        past_date = timezone.localdate() - timedelta(days=5)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Rufe Dashboard-View auf
        response = self.client.get("/")

        # Prüfe, dass die Lesson auf TAUGHT gesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")
        self.assertEqual(response.status_code, 200)

    def test_week_view_updates_past_lessons(self):
        """Test: Week-View aktualisiert vergangene Lessons automatisch."""
        # Erstelle eine vergangene Lesson mit Status PLANNED
        past_date = timezone.localdate() - timedelta(days=5)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Rufe Week-View auf
        response = self.client.get("/lessons/week/")

        # Prüfe, dass die Lesson auf TAUGHT gesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")
        self.assertEqual(response.status_code, 200)

    def test_income_overview_view_updates_past_lessons(self):
        """Test: Income-Overview-View aktualisiert vergangene Lessons automatisch."""
        # Erstelle eine vergangene Lesson mit Status PLANNED
        past_date = timezone.localdate() - timedelta(days=5)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Rufe Income-Overview-View auf
        response = self.client.get("/income/")

        # Prüfe, dass die Lesson auf TAUGHT gesetzt wurde
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")
        self.assertEqual(response.status_code, 200)

    def test_views_do_not_update_paid_lessons(self):
        """Test: Views ändern keine Lessons mit Status PAID."""
        # Erstelle eine vergangene Lesson mit Status PAID
        past_date = timezone.localdate() - timedelta(days=5)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )

        # Rufe Dashboard-View auf
        response = self.client.get("/")

        # Prüfe, dass die Lesson unverändert bleibt
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")
        self.assertEqual(response.status_code, 200)
