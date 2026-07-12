"""
Tests for selecting an Institute (or "No institute") on ContractForm.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract, Institute


class ContractFormInstituteSelectionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_bt", password="x")
        self.institute = Institute.objects.create(user=self.user, institute_name="TutorSpace")

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

    def test_no_institute_selected_saves_private_contract(self):
        form = ContractForm(data=self._base_data(institute_fk=""), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertIsNone(contract.institute_fk)
        self.assertIsNone(contract.institute)

    def test_institute_selected_saves_link(self):
        form = ContractForm(
            data=self._base_data(institute_fk=str(self.institute.pk)), user=self.user
        )
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertEqual(contract.institute_fk_id, self.institute.pk)
        self.assertEqual(contract.institute, "TutorSpace")

    def test_institute_dropdown_only_lists_own_institutes(self):
        other_user = User.objects.create_user(username="other_tutor", password="x")
        Institute.objects.create(user=other_user, institute_name="OtherInstitute")
        form = ContractForm(user=self.user)
        names = list(
            form.fields["institute_fk"].queryset.values_list("institute_name", flat=True)
        )
        self.assertEqual(names, ["TutorSpace"])

    def test_editing_existing_institute_contract_preselects_institute(self):
        contract = Contract.objects.create(
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
            institute_fk=self.institute,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        form = ContractForm(instance=contract, user=self.user)
        self.assertEqual(form.initial["institute_fk"], self.institute.pk)

    def test_editing_existing_private_contract_has_no_institute_preselected(self):
        contract = Contract.objects.create(
            user=self.user,
            first_name="Anna",
            last_name="Schmidt",
            institute_fk=None,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        form = ContractForm(instance=contract, user=self.user)
        self.assertIsNone(form.instance.institute_fk)
