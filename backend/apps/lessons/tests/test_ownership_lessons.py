"""
Ownership/tenant isolation tests for Lessons.
Tutor B cannot see/update/delete Tutor A's lessons. Recurring endpoints must return 404 for foreign pk.
"""

from datetime import date, time

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class LessonOwnershipIsolationTest(TestCase):
    """Tutor B cannot see/update/delete Tutor A's lessons. 404 on cross-user access."""

    def setUp(self):
        self.client = Client()
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")

        self.student_a = Student.objects.create(
            user=self.tutor_a,
            first_name="Alice",
            last_name="AStudent",
        )
        self.student_b = Student.objects.create(
            user=self.tutor_b,
            first_name="Bob",
            last_name="BStudent",
        )

        self.contract_a = Contract.objects.create(
            student=self.student_a,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            student=self.student_b,
            hourly_rate=25,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

        self.lesson_a = Lesson.objects.create(
            contract=self.contract_a,
            date=date(2025, 3, 10),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        self.lesson_b = Lesson.objects.create(
            contract=self.contract_b,
            date=date(2025, 3, 11),
            start_time=time(14, 0),
            duration_minutes=60,
            status="planned",
        )

    def test_tutor_a_list_shows_only_own_lessons(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("lessons:list"))
        self.assertEqual(response.status_code, 200)
        ids = [les.pk for les in response.context["lessons"]]
        self.assertIn(self.lesson_a.pk, ids)
        self.assertNotIn(self.lesson_b.pk, ids)

    def test_tutor_b_list_shows_only_own_lessons(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("lessons:list"))
        self.assertEqual(response.status_code, 200)
        ids = [les.pk for les in response.context["lessons"]]
        self.assertIn(self.lesson_b.pk, ids)
        self.assertNotIn(self.lesson_a.pk, ids)

    def test_tutor_a_can_view_own_lesson_detail(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("lessons:detail", kwargs={"pk": self.lesson_a.pk}))
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_lesson_detail(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("lessons:detail", kwargs={"pk": self.lesson_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_gets_404_for_tutor_a_lesson_update(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("lessons:update", kwargs={"pk": self.lesson_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_cannot_delete_tutor_a_lesson(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("lessons:delete", kwargs={"pk": self.lesson_a.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Lesson.objects.filter(pk=self.lesson_a.pk).exists())

    def test_tutor_b_gets_404_for_tutor_a_lesson_conflicts(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("lessons:conflicts", kwargs={"pk": self.lesson_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_week_view_shows_only_own_lessons(self):
        """Week view must only display tutor's own lessons."""
        self.client.force_login(self.tutor_a)
        response = self.client.get(
            reverse("lessons:week"),
            {"year": 2025, "month": 3, "day": 10},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Alice", content)
        self.assertNotIn("Bob", content)

    def test_calendar_view_shows_only_own_lessons(self):
        """Calendar view must only display tutor's own lessons."""
        self.client.force_login(self.tutor_a)
        response = self.client.get(
            reverse("lessons:calendar"),
            {"year": 2025, "month": 3},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Alice", content)
        self.assertNotIn("Bob", content)


class RecurringLessonOwnershipIsolationTest(TestCase):
    """Recurring lesson endpoints: 404 for foreign pk. Bulk edit must not affect foreign data."""

    def setUp(self):
        self.client = Client()
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")

        self.student_a = Student.objects.create(
            user=self.tutor_a,
            first_name="Alice",
            last_name="AStudent",
        )
        self.student_b = Student.objects.create(
            user=self.tutor_b,
            first_name="Bob",
            last_name="BStudent",
        )

        self.contract_a = Contract.objects.create(
            student=self.student_a,
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            student=self.student_b,
            hourly_rate=25,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

        self.recurring_a = RecurringLesson.objects.create(
            contract=self.contract_a,
            start_date=date(2025, 1, 6),
            end_date=date(2025, 6, 30),
            start_time=time(10, 0),
            duration_minutes=60,
            monday=True,
            tuesday=False,
            wednesday=False,
            thursday=False,
            friday=False,
            saturday=False,
            sunday=False,
            recurrence_type="weekly",
            is_active=True,
        )
        self.recurring_b = RecurringLesson.objects.create(
            contract=self.contract_b,
            start_date=date(2025, 1, 6),
            end_date=date(2025, 6, 30),
            start_time=time(14, 0),
            duration_minutes=60,
            monday=True,
            tuesday=False,
            wednesday=False,
            thursday=False,
            friday=False,
            saturday=False,
            sunday=False,
            recurrence_type="weekly",
            is_active=True,
        )

    def test_tutor_a_recurring_list_shows_only_own(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("lessons:recurring_list"))
        self.assertEqual(response.status_code, 200)
        ids = [r.pk for r in response.context["recurring_lessons"]]
        self.assertIn(self.recurring_a.pk, ids)
        self.assertNotIn(self.recurring_b.pk, ids)

    def test_tutor_b_gets_404_for_tutor_a_recurring_detail(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(
            reverse("lessons:recurring_detail", kwargs={"pk": self.recurring_a.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_gets_404_for_tutor_a_recurring_update(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(
            reverse("lessons:recurring_update", kwargs={"pk": self.recurring_a.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_cannot_delete_tutor_a_recurring(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("lessons:recurring_delete", kwargs={"pk": self.recurring_a.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(RecurringLesson.objects.filter(pk=self.recurring_a.pk).exists())

    def test_tutor_b_gets_404_for_tutor_a_recurring_generate(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(
            reverse("lessons:recurring_generate", kwargs={"pk": self.recurring_a.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)

    def test_bulk_edit_tutor_b_cannot_affect_tutor_a_recurring(self):
        """Bulk edit with recurring_ids from tutor_a must not delete/update tutor_a's data."""
        self.client.force_login(self.tutor_b)
        self.client.post(
            reverse("lessons:recurring_bulk_edit"),
            data={"recurring_ids": [self.recurring_a.pk], "action": "delete"},
            follow=True,
        )
        # Must either 404 or not delete; recurring_a must still exist
        self.assertTrue(RecurringLesson.objects.filter(pk=self.recurring_a.pk).exists())
