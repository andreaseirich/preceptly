"""
Ownership/tenant isolation tests for Contracts.
Tutor B cannot see/update/delete Tutor A's contracts. Form student dropdown only shows own students.
"""

from datetime import date
from decimal import Decimal

from apps.contracts.models import Contract
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class ContractOwnershipIsolationTest(TestCase):
    """Tutor B cannot see/update/delete Tutor A's contracts. 404 on cross-user access."""

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
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            student=self.student_b,
            hourly_rate=Decimal("25"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )

    def test_tutor_a_list_shows_only_own_contracts(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("contracts:list"))
        self.assertEqual(response.status_code, 200)
        ids = [c.pk for c in response.context["contracts"]]
        self.assertIn(self.contract_a.pk, ids)
        self.assertNotIn(self.contract_b.pk, ids)

    def test_tutor_b_list_shows_only_own_contracts(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("contracts:list"))
        self.assertEqual(response.status_code, 200)
        ids = [c.pk for c in response.context["contracts"]]
        self.assertIn(self.contract_b.pk, ids)
        self.assertNotIn(self.contract_a.pk, ids)

    def test_tutor_a_can_view_own_contract_detail(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("contracts:detail", kwargs={"pk": self.contract_a.pk}))
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_contract_detail(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("contracts:detail", kwargs={"pk": self.contract_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_a_can_update_own_contract(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("contracts:update", kwargs={"pk": self.contract_a.pk}))
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_contract_update(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("contracts:update", kwargs={"pk": self.contract_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_cannot_delete_tutor_a_contract(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("contracts:delete", kwargs={"pk": self.contract_a.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Contract.objects.filter(pk=self.contract_a.pk).exists())

    def test_create_form_student_dropdown_only_contains_own_students(self):
        """Contract create form: student field queryset must be filtered by user."""
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("contracts:create"))
        self.assertEqual(response.status_code, 200)
        # Student B must not appear as option (B belongs to tutor_b)
        content = response.content.decode()
        self.assertIn("Alice", content)
        self.assertIn("AStudent", content)
        self.assertNotIn("Bob", content)
        self.assertNotIn("BStudent", content)

    def test_update_form_student_dropdown_only_contains_own_students(self):
        """Contract update form: student field queryset must be filtered by user."""
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("contracts:update", kwargs={"pk": self.contract_a.pk}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Alice", content)
        self.assertNotIn("Bob", content)

    def test_create_rejects_foreign_student_via_post(self):
        """POST with student_id of tutor_b's student must fail (validation or 404)."""
        self.client.force_login(self.tutor_a)
        response = self.client.post(
            reverse("contracts:create"),
            data={
                "student": self.student_b.pk,
                "hourly_rate": "30",
                "unit_duration_minutes": "60",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "is_active": "on",
                "has_monthly_planning_limit": "on",
            },
            follow=True,
        )
        # Form validation should reject: choice not in queryset
        self.assertNotEqual(response.status_code, 302)
        self.assertEqual(Contract.objects.filter(student=self.student_b).count(), 1)
