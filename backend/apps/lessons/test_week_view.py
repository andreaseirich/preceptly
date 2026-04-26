"""
Tests für WeekView und WeekService.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.week_service import WeekService
from apps.students.models import Student


class WeekServiceTest(TestCase):
    """Tests für WeekService."""

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
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_get_week_data_returns_correct_week_range(self):
        """Test: WeekService gibt korrekten Wochenbereich zurück."""
        # 15. Januar 2025 ist ein Mittwoch
        week_data = WeekService.get_week_data(2025, 1, 15)

        # Woche sollte von Montag (13.1.) bis Sonntag (19.1.) gehen
        self.assertEqual(week_data["week_start"], date(2025, 1, 13))
        self.assertEqual(week_data["week_end"], date(2025, 1, 19))

    def test_get_week_data_includes_lessons_in_week(self):
        """Test: WeekService enthält Lessons innerhalb der Woche."""
        # Erstelle Lesson am Mittwoch (15.1.)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        week_data = WeekService.get_week_data(2025, 1, 15)

        self.assertIn(lesson.date, week_data["lessons_by_date"])
        self.assertIn(lesson, week_data["lessons_by_date"][lesson.date])

    def test_get_week_data_excludes_lessons_outside_week(self):
        """Test: WeekService schließt Lessons außerhalb der Woche aus."""
        # Erstelle Lesson am Montag der nächsten Woche (20.1.)
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 20),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        week_data = WeekService.get_week_data(2025, 1, 15)

        self.assertNotIn(lesson.date, week_data["lessons_by_date"])

    def test_get_week_data_includes_blocked_times(self):
        """Test: WeekService enthält Blockzeiten innerhalb der Woche."""
        blocked_time = BlockedTime.objects.create(
            user=self.user,
            title="Uni-Vorlesung",
            start_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 1, 15), time(10, 0))
            ),
            end_datetime=timezone.make_aware(
                timezone.datetime.combine(date(2025, 1, 15), time(12, 0))
            ),
        )

        week_data = WeekService.get_week_data(2025, 1, 15)

        self.assertIn(blocked_time.start_datetime.date(), week_data["blocked_times_by_date"])
        self.assertIn(
            blocked_time, week_data["blocked_times_by_date"][blocked_time.start_datetime.date()]
        )


class WeekViewTest(TestCase):
    """Tests für WeekView."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Setzt Testdaten auf."""
        self.client = Client()
        self.client.force_login(self.user)
        self.student = Student.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_week_view_loads_without_parameters(self):
        """Test: WeekView lädt ohne Parameter (verwendet aktuelles Datum)."""
        response = self.client.get("/lessons/week/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("weekdays", response.context)
        self.assertEqual(len(response.context["weekdays"]), 7)

    def test_week_view_loads_with_parameters(self):
        """Test: WeekView lädt mit year/month/day Parametern."""
        response = self.client.get("/lessons/week/?year=2025&month=1&day=15")
        self.assertEqual(response.status_code, 200)
        self.assertIn("week_start", response.context)
        self.assertEqual(response.context["week_start"], date(2025, 1, 13))  # Montag der Woche

    def test_week_view_navigation(self):
        """Test: WeekView hat Navigation für vorige/nächste Woche."""
        response = self.client.get("/lessons/week/?year=2025&month=1&day=15")
        self.assertEqual(response.status_code, 200)
        self.assertIn("prev_week", response.context)
        self.assertIn("next_week", response.context)
        self.assertEqual(response.context["prev_week"], date(2025, 1, 6))  # Vorige Woche
        self.assertEqual(response.context["next_week"], date(2025, 1, 20))  # Nächste Woche

    def test_week_view_includes_lessons(self):
        """Test: WeekView zeigt Lessons in der Woche."""
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        response = self.client.get("/lessons/week/?year=2025&month=1&day=15")
        self.assertEqual(response.status_code, 200)

        # Prüfe, ob Lesson in einem Wochentag enthalten ist
        weekdays = response.context["weekdays"]
        found = False
        for weekday in weekdays:
            if weekday["date"] == lesson.date:
                self.assertIn(lesson, weekday["lessons"])
                found = True
        self.assertTrue(found)


class LessonCreateViewWithStartEndTest(TestCase):
    """Tests für LessonCreateView mit start/end Parametern."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Setzt Testdaten auf."""
        self.client = Client()
        self.client.force_login(self.user)
        self.student = Student.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_lesson_create_view_accepts_start_end_parameters(self):
        """Test: LessonCreateView übernimmt start/end aus GET-Parametern."""
        # Simuliere Drag-to-Create: 15.1.2025, 14:00-15:00
        start = "2025-01-15T14:00"
        end = "2025-01-15T15:00"

        response = self.client.get(f"/lessons/create/?start={start}&end={end}")
        self.assertEqual(response.status_code, 200)

        # Prüfe, ob initiale Werte gesetzt sind
        form = response.context["form"]
        self.assertEqual(form.initial["date"], date(2025, 1, 15))
        self.assertEqual(form.initial["start_time"], time(14, 0))
        self.assertEqual(form.initial["duration_minutes"], 60)


class BlockedTimeCreateViewWithStartEndTest(TestCase):
    """Tests für BlockedTimeCreateView mit start/end Parametern."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser_bt", password="testpass123")
        self.client = Client()
        self.client.force_login(self.user)

    def test_blocked_time_create_view_accepts_start_end_parameters(self):
        """Test: BlockedTimeCreateView übernimmt start/end aus GET-Parametern."""
        # Simuliere Drag-to-Create: 15.1.2025, 10:00-12:00
        start = "2025-01-15T10:00"
        end = "2025-01-15T12:00"

        response = self.client.get(f"/blocked-times/create/?start={start}&end={end}")
        self.assertEqual(response.status_code, 200)

        # Prüfe, ob initiale Werte gesetzt sind
        form = response.context["form"]
        self.assertIn("start_datetime", form.initial)
        self.assertIn("end_datetime", form.initial)

        # Prüfe, dass Zeiten korrekt sind
        start_dt = form.initial["start_datetime"]
        end_dt = form.initial["end_datetime"]
        self.assertEqual(start_dt.date(), date(2025, 1, 15))
        self.assertEqual(start_dt.time(), time(10, 0))
        self.assertEqual(end_dt.time(), time(12, 0))
