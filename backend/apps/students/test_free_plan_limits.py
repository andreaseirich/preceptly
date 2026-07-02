"""
Tests for free-plan soft limits (student and invoice count warnings).

Rules:
- New free users (date_joined >= FREE_PLAN_LIMITS_SINCE): soft limit applies
- Existing free users (date_joined < FREE_PLAN_LIMITS_SINCE): grandfathered, no limits
- Paid users (starter/pro/business): no limits regardless of join date
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.feature_flags import (
    FREE_PLAN_LIMITS_SINCE,
    FREE_STUDENT_LIMIT,
    is_new_free_user,
)
from apps.core.models import UserProfile


def _make_new_free_user(username):
    """Create a free-plan user with date_joined after FREE_PLAN_LIMITS_SINCE."""
    user = User.objects.create_user(username=username, password="test")
    # Ensure date_joined is after the cutoff (it will be, since we just created the user)
    assert user.date_joined >= FREE_PLAN_LIMITS_SINCE, (
        f"Test user date_joined {user.date_joined} is not >= cutoff {FREE_PLAN_LIMITS_SINCE}; "
        "adjust FREE_PLAN_LIMITS_SINCE to be in the past for tests"
    )
    return user


def _make_old_free_user(username):
    """Create a free-plan user with date_joined before FREE_PLAN_LIMITS_SINCE (grandfathered)."""
    user = User.objects.create_user(username=username, password="test")
    old_date = FREE_PLAN_LIMITS_SINCE - timedelta(days=1)
    User.objects.filter(pk=user.pk).update(date_joined=old_date)
    user.refresh_from_db()
    return user


def _make_paid_user(username, tier="starter"):
    """Create a paid-plan user (exempt from free-plan limits)."""
    user = User.objects.create_user(username=username, password="test")
    # Create profile directly with the right tier (no signal does this automatically)
    UserProfile.objects.create(user=user, subscription_tier=tier)
    return user


def _make_student(user):
    return Contract.objects.create(
        user=user,
        first_name="Test",
        last_name="Student",
        hourly_rate=Decimal("20.00"),
        start_date=date.today(),
    )


class IsNewFreeUserTest(TestCase):
    def test_new_free_user_is_new(self):
        user = _make_new_free_user("new_free")
        self.assertTrue(is_new_free_user(user))

    def test_old_free_user_is_not_new(self):
        user = _make_old_free_user("old_free")
        self.assertFalse(is_new_free_user(user))

    def test_starter_user_is_not_new_free(self):
        user = _make_paid_user("starter_user", tier="starter")
        self.assertFalse(is_new_free_user(user))

    def test_pro_user_is_not_new_free(self):
        user = _make_paid_user("pro_user", tier="pro")
        self.assertFalse(is_new_free_user(user))


class StudentLimitWarningTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _post_new_student(self, user):
        self.client.force_login(user)
        return self.client.post(
            reverse("students:create"),
            {
                "first_name": "New",
                "last_name": "Student",
                "hourly_rate": "20.00",
                "unit_duration_minutes": "60",
                "start_date": date.today().isoformat(),
            },
        )

    def test_new_free_user_gets_warning_at_6th_student(self):
        """New free user with 5 existing students sees a warning when creating the 6th."""
        user = _make_new_free_user("new_free_limit")
        for i in range(FREE_STUDENT_LIMIT):
            _make_student(user)

        self.assertEqual(Contract.objects.filter(user=user).count(), FREE_STUDENT_LIMIT)

        response = self._post_new_student(user)

        # Student was created (no block)
        self.assertEqual(Contract.objects.filter(user=user).count(), FREE_STUDENT_LIMIT + 1)

        # Warning message present
        msgs = list(response.wsgi_request._messages)
        warning_msgs = [m for m in msgs if m.level_tag == "warning"]
        self.assertTrue(
            any("5" in str(m) or "limit" in str(m).lower() for m in warning_msgs),
            f"Expected student limit warning, got messages: {[str(m) for m in msgs]}",
        )

    def test_old_free_user_no_warning_beyond_limit(self):
        """Grandfathered free user (joined before cutoff) gets no warning even with 6+ students."""
        user = _make_old_free_user("old_free_limit")
        for i in range(FREE_STUDENT_LIMIT):
            _make_student(user)

        response = self._post_new_student(user)

        # Student was created
        self.assertEqual(Contract.objects.filter(user=user).count(), FREE_STUDENT_LIMIT + 1)

        # No warning about the limit
        msgs = list(response.wsgi_request._messages)
        warning_msgs = [m for m in msgs if m.level_tag == "warning"]
        self.assertFalse(
            any("limit" in str(m).lower() or "free plan" in str(m).lower() for m in warning_msgs),
            f"Grandfathered user should not get a limit warning, got: {[str(m) for m in msgs]}",
        )

    def test_starter_user_no_warning_beyond_limit(self):
        """Starter/paid user gets no warning even with 6+ students."""
        user = _make_paid_user("starter_limit")
        for i in range(FREE_STUDENT_LIMIT):
            _make_student(user)

        response = self._post_new_student(user)

        # Student was created
        self.assertEqual(Contract.objects.filter(user=user).count(), FREE_STUDENT_LIMIT + 1)

        # No limit warning
        msgs = list(response.wsgi_request._messages)
        warning_msgs = [m for m in msgs if m.level_tag == "warning"]
        self.assertFalse(
            any("limit" in str(m).lower() or "free plan" in str(m).lower() for m in warning_msgs),
            f"Paid user should not get a limit warning, got: {[str(m) for m in msgs]}",
        )

    def test_new_free_user_below_limit_no_warning(self):
        """New free user below the student limit gets no limit warning."""
        user = _make_new_free_user("new_free_under")
        for i in range(FREE_STUDENT_LIMIT - 1):
            _make_student(user)

        response = self._post_new_student(user)

        # Student was created
        self.assertEqual(Contract.objects.filter(user=user).count(), FREE_STUDENT_LIMIT)

        msgs = list(response.wsgi_request._messages)
        warning_msgs = [m for m in msgs if m.level_tag == "warning"]
        self.assertFalse(
            any("limit" in str(m).lower() or "free plan" in str(m).lower() for m in warning_msgs),
            f"User below limit should not get a warning, got: {[str(m) for m in msgs]}",
        )
