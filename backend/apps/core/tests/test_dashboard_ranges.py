"""
Tests für Dashboard-Bereiche (Today vs. Next 7 days).
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.services import LessonQueryService
from apps.students.models import Student


class DashboardRangesTest(TestCase):
    """Tests für die Trennung von Today- und Next-7-days-Bereichen im Dashboard."""

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

    def test_today_lesson_in_today_section_only(self):
        """Test: Lesson mit Datum = heute erscheint nur im Today-Bereich, nicht in Next 7 days."""
        today = timezone.now().date()

        # Erstelle eine Lesson für heute
        today_lesson = Lesson.objects.create(
            contract=self.contract,
            date=today,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe get_today_lessons
        today_lessons = LessonQueryService.get_today_lessons()
        self.assertIn(today_lesson, today_lessons)

        # Prüfe get_upcoming_lessons (sollte heute NICHT enthalten)
        upcoming_lessons = LessonQueryService.get_upcoming_lessons(days=7)
        self.assertNotIn(today_lesson, upcoming_lessons)

    def test_tomorrow_lesson_in_next_7_days(self):
        """Test: Lesson mit Datum = morgen erscheint in Next 7 days."""
        tomorrow = timezone.now().date() + timedelta(days=1)

        # Erstelle eine Lesson für morgen
        tomorrow_lesson = Lesson.objects.create(
            contract=self.contract,
            date=tomorrow,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe get_today_lessons (sollte morgen NICHT enthalten)
        today_lessons = LessonQueryService.get_today_lessons()
        self.assertNotIn(tomorrow_lesson, today_lessons)

        # Prüfe get_upcoming_lessons (sollte morgen enthalten)
        upcoming_lessons = LessonQueryService.get_upcoming_lessons(days=7)
        self.assertIn(tomorrow_lesson, upcoming_lessons)

    def test_lesson_beyond_7_days_not_in_next_7_days(self):
        """Test: Lesson mit Datum > heute + 7 Tage erscheint nicht in Next 7 days."""
        future_date = timezone.now().date() + timedelta(days=8)

        # Erstelle eine Lesson für in 8 Tagen
        future_lesson = Lesson.objects.create(
            contract=self.contract,
            date=future_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe get_today_lessons (sollte nicht enthalten)
        today_lessons = LessonQueryService.get_today_lessons()
        self.assertNotIn(future_lesson, today_lessons)

        # Prüfe get_upcoming_lessons (sollte nicht enthalten)
        upcoming_lessons = LessonQueryService.get_upcoming_lessons(days=7)
        self.assertNotIn(future_lesson, upcoming_lessons)

    def test_lesson_exactly_7_days_in_next_7_days(self):
        """Test: Lesson mit Datum = heute + 7 Tage erscheint in Next 7 days."""
        seven_days_later = timezone.now().date() + timedelta(days=7)

        # Erstelle eine Lesson für in genau 7 Tagen
        lesson_7_days = Lesson.objects.create(
            contract=self.contract,
            date=seven_days_later,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Prüfe get_upcoming_lessons (sollte enthalten sein, da date__lte verwendet wird)
        upcoming_lessons = LessonQueryService.get_upcoming_lessons(days=7)
        self.assertIn(lesson_7_days, upcoming_lessons)

    def test_dashboard_view_separation(self):
        """Test: Dashboard-View trennt korrekt zwischen Today und Next 7 days."""
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        # Erstelle Lessons
        today_lesson = Lesson.objects.create(
            contract=self.contract,
            date=today,
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )
        tomorrow_lesson = Lesson.objects.create(
            contract=self.contract,
            date=tomorrow,
            start_time=time(15, 0),
            duration_minutes=60,
            status="planned",
        )

        # Rufe Dashboard-View auf
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        context = response.context

        # Prüfe, dass today_lesson nur in today_lessons ist
        self.assertIn(today_lesson, context["today_lessons"])
        self.assertNotIn(today_lesson, context["upcoming_lessons"])

        # Prüfe, dass tomorrow_lesson nur in upcoming_lessons ist
        self.assertNotIn(tomorrow_lesson, context["today_lessons"])
        self.assertIn(tomorrow_lesson, context["upcoming_lessons"])
