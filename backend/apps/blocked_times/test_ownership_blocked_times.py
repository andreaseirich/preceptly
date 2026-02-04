"""
Ownership/tenant isolation tests for BlockedTimes.
Tutor B cannot see/update/delete Tutor A's blocked times. Same for RecurringBlockedTime.
"""

from datetime import date, datetime, time, timedelta

from apps.blocked_times.models import BlockedTime
from apps.blocked_times.recurring_models import RecurringBlockedTime
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone


class BlockedTimeOwnershipIsolationTest(TestCase):
    """Tutor B cannot see/update/delete Tutor A's blocked times. 404 on cross-user access."""

    def setUp(self):
        self.client = Client()
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")

        base = timezone.make_aware(datetime(2025, 3, 10, 9, 0))
        self.bt_a = BlockedTime.objects.create(
            user=self.tutor_a,
            title="A's blocked time",
            start_datetime=base,
            end_datetime=base + timedelta(hours=1),
        )
        self.bt_b = BlockedTime.objects.create(
            user=self.tutor_b,
            title="B's blocked time",
            start_datetime=base + timedelta(days=1),
            end_datetime=base + timedelta(days=1, hours=1),
        )

    def test_tutor_a_can_view_own_blocked_time_detail(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("blocked_times:detail", kwargs={"pk": self.bt_a.pk}))
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_blocked_time_detail(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("blocked_times:detail", kwargs={"pk": self.bt_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_a_can_update_own_blocked_time(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("blocked_times:update", kwargs={"pk": self.bt_a.pk}))
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_blocked_time_update(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("blocked_times:update", kwargs={"pk": self.bt_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_cannot_delete_tutor_a_blocked_time(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("blocked_times:delete", kwargs={"pk": self.bt_a.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(BlockedTime.objects.filter(pk=self.bt_a.pk).exists())


class RecurringBlockedTimeOwnershipIsolationTest(TestCase):
    """Tutor B cannot see/update/delete/generate Tutor A's recurring blocked times. 404 on cross-user."""

    def setUp(self):
        self.client = Client()
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")

        self.rbt_a = RecurringBlockedTime.objects.create(
            user=self.tutor_a,
            title="A's recurring",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 6, 30),
            start_time=time(9, 0),
            end_time=time(10, 0),
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
        self.rbt_b = RecurringBlockedTime.objects.create(
            user=self.tutor_b,
            title="B's recurring",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 6, 30),
            start_time=time(14, 0),
            end_time=time(15, 0),
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

    def test_tutor_a_can_view_own_recurring_blocked_time_detail(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(
            reverse("blocked_times:recurring_detail", kwargs={"pk": self.rbt_a.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_recurring_detail(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(
            reverse("blocked_times:recurring_detail", kwargs={"pk": self.rbt_a.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_gets_404_for_tutor_a_recurring_update(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(
            reverse("blocked_times:recurring_update", kwargs={"pk": self.rbt_a.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_cannot_delete_tutor_a_recurring_blocked_time(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("blocked_times:recurring_delete", kwargs={"pk": self.rbt_a.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(RecurringBlockedTime.objects.filter(pk=self.rbt_a.pk).exists())

    def test_tutor_b_gets_404_for_tutor_a_recurring_generate_get(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(
            reverse("blocked_times:recurring_generate", kwargs={"pk": self.rbt_a.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_gets_404_for_tutor_a_recurring_generate_post(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("blocked_times:recurring_generate", kwargs={"pk": self.rbt_a.pk}),
            data={"check_conflicts": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
