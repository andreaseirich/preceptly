"""
Tests für Kalender-Integration (Create mit Datum, Filterung).
"""

from datetime import date, time, timedelta
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.views import LessonCreateView
from apps.students.models import Student
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User


class CalendarIntegrationTest(TestCase):
    """Tests für Kalender-Integration."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Lisa", last_name="Müller", email="lisa@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_create_lesson_with_date_parameter(self):
        """Test: Lesson erstellen mit Datum aus Query-Parameter."""
        today = timezone.localdate()
        future_date = today + timedelta(days=7)

        # Simuliere Request mit date-Parameter
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get(f"/lessons/create/?date={future_date}")

        view = LessonCreateView()
        view.request = request
        view.setup(request)

        initial = view.get_initial()
        self.assertEqual(initial["date"], future_date)

    def test_calendar_redirect_after_create(self):
        """Test: Nach Lesson-Erstellung Weiterleitung zum Kalender."""
        today = timezone.localdate()
        future_date = today + timedelta(days=5)

        lesson = Lesson.objects.create(
            contract=self.contract,
            date=future_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        from django.test import RequestFactory

        request = RequestFactory().get("/lessons/create/")
        request.session = {
            "last_calendar_view": "calendar",
            "last_calendar_year": future_date.year,
            "last_calendar_month": future_date.month,
        }
        request.user = self.user
        view = LessonCreateView()
        view.request = request
        view.setup(request)
        view.object = lesson

        success_url = view.get_success_url()
        expected_url = f"/lessons/calendar/?year={future_date.year}&month={future_date.month}"
        self.assertIn(expected_url, success_url)
