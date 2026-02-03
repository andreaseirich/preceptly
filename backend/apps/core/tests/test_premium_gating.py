"""
Tests for Premium feature gating and Reports page.
"""

from decimal import Decimal

from apps.contracts.models import Contract
from apps.core.feature_flags import (
    PUBLIC_BOOKING_MONTHLY_LIMIT,
    Feature,
    public_booking_limit_reached,
    user_has_feature,
)
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class FeatureFlagsTest(TestCase):
    """Tests for feature flag helpers."""

    def setUp(self):
        self.basic_user = User.objects.create_user(username="basic", password="test")
        UserProfile.objects.create(user=self.basic_user, is_premium=False)
        self.premium_user = User.objects.create_user(username="premium", password="test")
        UserProfile.objects.create(user=self.premium_user, is_premium=True)

    def test_basic_has_no_premium_features(self):
        self.assertFalse(user_has_feature(self.basic_user, Feature.FEATURE_PUBLIC_RESCHEDULE))
        self.assertFalse(user_has_feature(self.basic_user, Feature.FEATURE_REPORTS))
        self.assertFalse(user_has_feature(self.basic_user, Feature.FEATURE_BILLING_PRO))
        self.assertFalse(user_has_feature(self.basic_user, Feature.FEATURE_AI_LESSON_PLANS))

    def test_premium_has_all_features(self):
        self.assertTrue(user_has_feature(self.premium_user, Feature.FEATURE_PUBLIC_RESCHEDULE))
        self.assertTrue(user_has_feature(self.premium_user, Feature.FEATURE_REPORTS))
        self.assertTrue(user_has_feature(self.premium_user, Feature.FEATURE_BILLING_PRO))
        self.assertTrue(user_has_feature(self.premium_user, Feature.FEATURE_AI_LESSON_PLANS))

    def test_public_booking_limit_reached_basic(self):
        from datetime import date

        student = Student.objects.create(user=self.basic_user, first_name="A", last_name="B")
        contract = Contract.objects.create(
            student=student,
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        from django.utils import timezone

        now = timezone.now()
        for _ in range(PUBLIC_BOOKING_MONTHLY_LIMIT):
            Lesson.objects.create(
                contract=contract,
                date=now.date(),
                start_time="10:00",
                duration_minutes=60,
                status="planned",
                created_via="public_booking",
            )
        self.assertTrue(public_booking_limit_reached(self.basic_user))
        self.assertFalse(public_booking_limit_reached(self.premium_user))

    def test_reports_page_basic_teaser(self):
        self.client.login(username="basic", password="test")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Premium")
        self.assertContains(response, "Upgrade")

    def test_reports_page_premium_full(self):
        self.client.login(username="premium", password="test")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hours")
