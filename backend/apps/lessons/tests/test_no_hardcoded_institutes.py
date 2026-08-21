"""
Regression test: the tutor-no-show checkbox label/help text and the
InvoiceItem amount help text must not hardcode specific institute names
(e.g. "TutorSpace", "Abacus") - institutes are freely named per tutor,
so any tutor without those exact institute names would see confusing,
inapplicable UI copy on both the lesson create and update pages.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase

from apps.billing.models import InvoiceItem
from apps.contracts.models import Contract
from apps.lessons.forms import LessonForm
from apps.lessons.models import Lesson, Session


class NoHardcodedInstituteNamesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 6, 2),
            start_time=time(10, 0),
            duration_minutes=60,
        )
        self.client = Client()
        self.client.login(username="tutor", password="pass")

    def _assert_no_hardcoded_names(self, text):
        for name in ("TutorSpace", "Abacus"):
            self.assertNotIn(name, text, f"UI text should not hardcode institute '{name}'")

    def test_form_label_has_no_hardcoded_institute_names(self):
        form = LessonForm(user=self.user)
        self._assert_no_hardcoded_names(str(form.fields["tutor_no_show"].label))

    def test_session_model_help_text_has_no_hardcoded_institute_names(self):
        help_text = Session._meta.get_field("tutor_no_show").help_text
        self._assert_no_hardcoded_names(str(help_text))

    def test_invoiceitem_amount_help_text_has_no_hardcoded_institute_names(self):
        help_text = InvoiceItem._meta.get_field("amount").help_text
        self._assert_no_hardcoded_names(str(help_text))

    def test_lesson_create_page_has_no_hardcoded_institute_names(self):
        response = self.client.get("/lessons/create/")
        self.assertEqual(response.status_code, 200)
        self._assert_no_hardcoded_names(response.content.decode())

    def test_lesson_update_page_has_no_hardcoded_institute_names(self):
        response = self.client.get(f"/lessons/{self.lesson.pk}/update/")
        self.assertEqual(response.status_code, 200)
        self._assert_no_hardcoded_names(response.content.decode())
