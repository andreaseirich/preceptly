from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.models import Contract


class ContractModelTest(TestCase):
    """Tests für das Contract-Model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="tutor_contracts", password="test")
        self.student = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
        )

    def test_create_contract(self):
        """Test: Contract kann erstellt werden."""
        contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date.today(),
        )
        # student IS the contract after merge
        self.assertIsNotNone(contract)
        self.assertEqual(contract.hourly_rate, Decimal("25.00"))
        self.assertTrue(contract.is_active)

    def test_contract_relationship_to_student(self):
        """Test: Beziehung zwischen Contract und Student."""
        contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            hourly_rate=Decimal("30.00"),
            start_date=date.today(),
        )
        self.assertIsNotNone(contract)

    def test_contract_with_institute(self):
        """Test: Contract mit Institut."""
        contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            institute="Nachhilfe-Institut XY",
            hourly_rate=Decimal("35.00"),
            start_date=date.today(),
        )
        self.assertEqual(contract.institute, "Nachhilfe-Institut XY")
        self.assertIn("Nachhilfe-Institut XY", str(contract))
