"""
Tests für Konflikt-Details und Kalender mit vergangenen Lessons.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.calendar_service import CalendarService
from apps.lessons.models import Lesson
from apps.lessons.views import CalendarView
from apps.students.models import Student
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone
from django.contrib.auth.models import User


class ConflictDetailTest(TestCase):
    """Tests für Konflikt-Detailansicht."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student1 = Student.objects.create(
            user=self.user, first_name="Max", last_name="Mustermann", email="max@example.com"
        )
        self.student2 = Student.objects.create(
            user=self.user, first_name="Lisa", last_name="Müller", email="lisa@example.com"
        )
        self.contract1 = Contract.objects.create(
            student=self.student1,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract2 = Contract.objects.create(
            student=self.student2,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.factory = RequestFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_conflict_detail_view_shows_conflicting_lessons(self):
        """Test: ConflictDetailView zeigt kollidierende Lessons."""
        # Erstelle zwei kollidierende Lessons
        lesson1 = Lesson.objects.create(
            contract=self.contract1,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
        )
        lesson2 = Lesson.objects.create(
            contract=self.contract2,
            date=date(2025, 8, 15),
            start_time=time(14, 30),  # Überschneidung
            duration_minutes=60,
        )

        response = self.client.get(f"/lessons/{lesson1.pk}/conflicts/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("conflict_lessons", response.context)
        self.assertIn(lesson2, response.context["conflict_lessons"])

    def test_lesson_detail_view_shows_conflicts(self):
        """Test: LessonDetailView zeigt Konflikte."""
        lesson1 = Lesson.objects.create(
            contract=self.contract1,
            date=date(2025, 8, 15),
            start_time=time(14, 0),
            duration_minutes=60,
        )
        lesson2 = Lesson.objects.create(
            contract=self.contract2,
            date=date(2025, 8, 15),
            start_time=time(14, 30),
            duration_minutes=60,
        )

        response = self.client.get(f"/lessons/{lesson1.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_conflicts"])
        self.assertIn(lesson2, response.context["conflict_lessons"])


class CalendarPastLessonsTest(TestCase):
    """Tests für Kalender mit vergangenen Lessons."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.student = Student.objects.create(
            user=self.user, first_name="Test", last_name="Student", email="test@example.com"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_calendar_service_includes_past_lessons(self):
        """Test: CalendarService liefert sowohl vergangene als auch zukünftige Lessons."""
        today = timezone.localdate()
        past_date = today - timedelta(days=10)
        future_date = today + timedelta(days=10)

        # Erstelle vergangene und zukünftige Lessons
        Lesson.objects.create(
            contract=self.contract, date=past_date, start_time=time(14, 0), duration_minutes=60
        )
        Lesson.objects.create(
            contract=self.contract, date=future_date, start_time=time(15, 0), duration_minutes=60
        )

        # Lade Kalenderdaten für den aktuellen Monat
        calendar_data = CalendarService.get_calendar_data(today.year, today.month)

        # Prüfe, dass beide Lessons enthalten sind (wenn im Monat)
        all_lessons = []
        for lessons_list in calendar_data["lessons_by_date"].values():
            all_lessons.extend(lessons_list)

        lesson_dates = [lesson.date for lesson in all_lessons]

        # Wenn past_date im aktuellen Monat liegt, sollte es enthalten sein
        if past_date.year == today.year and past_date.month == today.month:
            self.assertIn(past_date, lesson_dates)

        # Wenn future_date im aktuellen Monat liegt, sollte es enthalten sein
        if future_date.year == today.year and future_date.month == today.month:
            self.assertIn(future_date, lesson_dates)

    def test_calendar_view_shows_past_lessons(self):
        """Test: CalendarView zeigt vergangene Lessons."""
        today = timezone.localdate()
        past_date = today - timedelta(days=5)

        # Stelle sicher, dass past_date im aktuellen Monat liegt
        if past_date.month != today.month:
            past_date = date(today.year, today.month, 1)

        lesson = Lesson.objects.create(
            contract=self.contract, date=past_date, start_time=time(14, 0), duration_minutes=60
        )

        request = RequestFactory().get(f"/lessons/calendar/?year={today.year}&month={today.month}")
        request.session = {}
        request.user = self.user
        view = CalendarView()
        view.request = request
        view.setup(request)

        context = view.get_context_data()

        # Prüfe, dass Lesson im Kalender enthalten ist
        all_lessons = []
        for week in context["weeks"]:
            for day in week:
                if day is not None:
                    all_lessons.extend(day["lessons"])

        lesson_ids = [lesson.id for lesson in all_lessons]
        self.assertIn(lesson.id, lesson_ids)
