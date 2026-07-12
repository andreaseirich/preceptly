"""
Tests for the Institut/Privat billing_type toggle on ContractForm.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract


class ContractFormBillingTypeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_bt", password="x")

    def _base_data(self, **overrides):
        data = {
            "first_name": "Anna",
            "last_name": "Schmidt",
            "hourly_rate": "25.00",
            "unit_duration_minutes": "60",
            "start_date": "2025-01-01",
            "has_monthly_planning_limit": "on",
        }
        data.update(overrides)
        return data

    def test_private_mode_clears_institute(self):
        form = ContractForm(
            data=self._base_data(billing_type="private", institute="Should be ignored"),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertEqual(contract.institute, "")

    def test_institute_mode_requires_institute_name(self):
        form = ContractForm(
            data=self._base_data(billing_type="institute", institute=""),
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("institute", form.errors)

    def test_institute_mode_saves_institute_name(self):
        form = ContractForm(
            data=self._base_data(billing_type="institute", institute="TutorSpace"),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertEqual(contract.institute, "TutorSpace")

    def test_editing_existing_institute_contract_defaults_to_institute_mode(self):
        contract = Contract.objects.create(
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
            institute="TutorSpace",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        form = ContractForm(instance=contract, user=self.user)
        self.assertEqual(form.fields["billing_type"].initial, ContractForm.BILLING_TYPE_INSTITUTE)

    def test_editing_existing_private_contract_defaults_to_private_mode(self):
        contract = Contract.objects.create(
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
            institute="",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        form = ContractForm(instance=contract, user=self.user)
        self.assertEqual(form.fields["billing_type"].initial, ContractForm.BILLING_TYPE_PRIVATE)
