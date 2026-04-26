from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.models import Contract
from apps.lessons.forms import SessionForm
from apps.lessons.models import Lesson
from apps.students.models import Student


class SessionFormContractActiveFilterTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_form", password="x")
        self.student = Student.objects.create(user=self.user, first_name="A", last_name="B")
        self.active_contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )
        self.inactive_contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=False,
        )

    def test_create_form_shows_only_active_contracts(self):
        form = SessionForm(user=self.user)
        self.assertIn(self.active_contract, form.fields["contract"].queryset)
        self.assertNotIn(self.inactive_contract, form.fields["contract"].queryset)

    def test_edit_form_keeps_existing_inactive_contract_selectable(self):
        lesson = Lesson.objects.create(
            contract=self.inactive_contract,
            date=date(2025, 2, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )
        form = SessionForm(instance=lesson, user=self.user)
        self.assertIn(self.inactive_contract, form.fields["contract"].queryset)

    def test_create_rejects_inactive_contract_server_side(self):
        form = SessionForm(
            data={
                "contract": self.inactive_contract.id,
                "date": "2025-02-01",
                "start_time": "10:00",
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "notes": "",
                "tutor_no_show": False,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("contract", form.errors)
