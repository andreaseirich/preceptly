"""
Tests for Premium feature gating and Reports page.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.feature_flags import (
    Feature,
    user_has_feature,
)
from apps.core.models import UserProfile


class FeatureFlagsTest(TestCase):
    """Tests for feature flag helpers."""

    def setUp(self):
        self.basic_user = User.objects.create_user(username="basic", password="test")
        UserProfile.objects.create(user=self.basic_user, is_premium=False)
        self.premium_user = User.objects.create_user(username="premium", password="test")
        UserProfile.objects.create(user=self.premium_user, is_premium=True, subscription_tier="pro")

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
