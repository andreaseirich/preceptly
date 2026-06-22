from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.core.selectors import IncomeSelector
from apps.lessons.models import Lesson


class UserProfileModelTest(TestCase):
    """Tests für das UserProfile-Model."""

    def test_create_user_profile(self):
        """Test: UserProfile kann erstellt werden."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        profile = UserProfile.objects.create(user=user, is_premium=True, subscription_tier="pro")
        self.assertEqual(profile.user, user)
        self.assertTrue(profile.is_premium)
        self.assertIn("Premium", str(profile))


class IncomeSelectorTest(TestCase):
    """Tests für den IncomeSelector."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        """Set up test data."""
        self.student = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
        )
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            hourly_rate=Decimal("25.00"),
            start_date=date(2025, 1, 1),
        )

    def test_monthly_income_calculation(self):
        """Test: Monatliche Einnahmenberechnung."""
        # Erstelle Lessons im Januar 2025
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 15),
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 22),
            start_time=time(14, 0),
            duration_minutes=60,
            status="paid",
        )

        result = IncomeSelector.get_monthly_income(2025, 1, "paid")
        self.assertEqual(result["year"], 2025)
        self.assertEqual(result["month"], 1)
        self.assertEqual(result["lesson_count"], 2)
        # 2 Lessons * 25€ = 50€
        self.assertEqual(result["total_income"], Decimal("50.00"))

    def test_monthly_income_empty(self):
        """Test: Monatliche Einnahmen ohne Lessons."""
        result = IncomeSelector.get_monthly_income(2025, 1, "paid")
        self.assertEqual(result["total_income"], Decimal("0.00"))
        self.assertEqual(result["lesson_count"], 0)
