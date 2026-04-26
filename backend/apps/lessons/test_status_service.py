"""
Tests für LessonStatusUpdater.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.status_service import LessonStatusUpdater
from apps.students.models import Student
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User


class LessonStatusUpdaterTest(TestCase):
    """Tests für LessonStatusService."""

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
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_update_past_lessons_to_taught(self):
        """Test: Vergangene Lesson mit Status PLANNED wird auf TAUGHT gesetzt."""
        # Erstelle eine Lesson, die vor 5 Tagen endete
        past_date = timezone.localdate() - timedelta(days=5)
        past_time = time(14, 0)

        lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time=past_time,
            duration_minutes=60,
            status="planned",
        )

        # Berechne end_datetime
        start_datetime = timezone.make_aware(datetime.combine(past_date, past_time))
        end_datetime = start_datetime + timedelta(minutes=60)

        # Stelle sicher, dass end_datetime in der Vergangenheit liegt
        now = timezone.now()
        self.assertLess(end_datetime, now, "Test-Lesson sollte in der Vergangenheit liegen")

        updated_count = LessonStatusUpdater.update_past_lessons_to_taught()

        self.assertEqual(updated_count, 1)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")

    def test_update_past_lessons_future_lesson_not_updated(self):
        """Test: Zukünftige Lesson mit Status PLANNED bleibt PLANNED."""
        future_date = timezone.localdate() + timedelta(days=5)
        future_time = time(14, 0)

        lesson = Lesson.objects.create(
            contract=self.contract,
            date=future_date,
            start_time=future_time,
            duration_minutes=60,
            status="planned",
        )

        updated_count = LessonStatusUpdater.update_past_lessons_to_taught()

        self.assertEqual(updated_count, 0)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "planned")

    def test_update_past_lessons_paid_not_updated(self):
        """Test: Lesson mit Status PAID wird nicht verändert, auch wenn in der Vergangenheit."""
        past_date = timezone.localdate() - timedelta(days=5)

        lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )

        updated_count = LessonStatusUpdater.update_past_lessons_to_taught()

        self.assertEqual(updated_count, 0)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "paid")

    def test_update_past_lessons_cancelled_not_updated(self):
        """Test: Lesson mit Status CANCELLED wird nicht verändert, auch wenn in der Vergangenheit."""
        past_date = timezone.localdate() - timedelta(days=5)

        lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time=time(14, 0),
            duration_minutes=60,
            status="cancelled",
        )

        updated_count = LessonStatusUpdater.update_past_lessons_to_taught()

        self.assertEqual(updated_count, 0)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "cancelled")

    def test_update_past_lessons_bulk_update(self):
        """Test: update_past_lessons_to_taught aktualisiert mehrere Lessons gleichzeitig."""
        past_date = timezone.localdate() - timedelta(days=10)

        # Erstelle mehrere vergangene Lessons mit Status PLANNED
        past_lessons = []
        for i in range(3):
            lesson = Lesson.objects.create(
                contract=self.contract,
                date=past_date - timedelta(days=i),
                start_time=time(14, 0),
                duration_minutes=60,
                status="planned",
            )
            past_lessons.append(lesson)

        # Erstelle eine zukünftige Lesson (sollte nicht aktualisiert werden)
        future_lesson = Lesson.objects.create(
            contract=self.contract,
            date=timezone.localdate() + timedelta(days=5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

        # Erstelle eine vergangene Lesson mit Status PAID (sollte nicht aktualisiert werden)
        paid_lesson = Lesson.objects.create(
            contract=self.contract,
            date=past_date - timedelta(days=5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )

        updated_count = LessonStatusUpdater.update_past_lessons_to_taught()

        self.assertEqual(updated_count, 3)

        # Prüfe, dass alle vergangenen PLANNED Lessons auf TAUGHT gesetzt wurden
        for lesson in past_lessons:
            lesson.refresh_from_db()
            self.assertEqual(lesson.status, "taught")

        # Prüfe, dass zukünftige Lesson unverändert bleibt
        future_lesson.refresh_from_db()
        self.assertEqual(future_lesson.status, "planned")

        # Prüfe, dass PAID Lesson unverändert bleibt
        paid_lesson.refresh_from_db()
        self.assertEqual(paid_lesson.status, "paid")

    def test_update_past_lessons_with_custom_now(self):
        """Test: update_past_lessons_to_taught funktioniert mit custom now-Parameter."""
        # Erstelle eine Lesson, die in 1 Stunde endet
        now = timezone.now()
        lesson_date = timezone.localdate()
        lesson_time = (timezone.localtime(now) + timedelta(hours=1)).time()

        lesson = Lesson.objects.create(
            contract=self.contract,
            date=lesson_date,
            start_time=lesson_time,
            duration_minutes=60,
            status="planned",
        )

        # Setze now auf 2 Stunden + 1 Sekunde in der Zukunft (Lesson endet exakt um now+2h)
        future_now = now + timedelta(hours=2, seconds=1)

        updated_count = LessonStatusUpdater.update_past_lessons_to_taught(now=future_now)

        self.assertEqual(updated_count, 1)
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, "taught")
