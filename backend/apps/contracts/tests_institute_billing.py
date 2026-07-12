from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.institute_billing import (
    calculate_lesson_amount,
    resolve_institute_billing_config,
)
from apps.contracts.models import Contract, Institute
from apps.lessons.models import Lesson


class ResolveInstituteBillingConfigTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_ib", password="x")

    def test_no_institute_returns_none(self):
        self.assertIsNone(resolve_institute_billing_config(None))

    def test_institute_without_tiers_or_no_show_flag_returns_none(self):
        institute = Institute.objects.create(user=self.tutor, institute_name="PlainInstitute")
        self.assertIsNone(resolve_institute_billing_config(institute))

    def test_institute_with_explicit_tiers_and_no_show_flag(self):
        institute = Institute.objects.create(
            user=self.tutor,
            institute_name="MyInstitute",
            tiers=[
                {"hours_from": 0, "rate": 10, "label": "10 €/h"},
                {"hours_from": 20, "rate": 12, "label": "12 €/h"},
            ],
            unpaid_on_tutor_no_show=True,
        )
        config = resolve_institute_billing_config(institute)
        self.assertIsNotNone(config)
        self.assertEqual(len(config.tiers), 2)
        self.assertTrue(config.unpaid_on_tutor_no_show)

    def test_config_with_only_no_show_flag_and_no_tiers(self):
        institute = Institute.objects.create(
            user=self.tutor,
            institute_name="NoShowOnlyInstitute",
            tiers=[],
            unpaid_on_tutor_no_show=True,
        )
        config = resolve_institute_billing_config(institute)
        self.assertIsNotNone(config)
        self.assertIsNone(config.tiers)
        self.assertTrue(config.unpaid_on_tutor_no_show)


class CalculateLessonAmountGenericInstituteTest(TestCase):
    """Any institute a tutor creates gets tiered/no-show billing purely from its own
    stored configuration — no institute name is special-cased."""

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_generic", password="x")
        self.institute = Institute.objects.create(
            user=self.tutor,
            institute_name="MyInstitute",
            tiers=[
                {"hours_from": 0, "rate": 10, "label": "10 €/h"},
                {"hours_from": 2, "rate": 12, "label": "12 €/h"},
            ],
        )
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="A",
            last_name="S",
            institute_fk=self.institute,
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )

    def test_tiered_amount_below_threshold(self):
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.assertEqual(calculate_lesson_amount(lesson, self.tutor), Decimal("10.00"))

    def test_tiered_amount_after_crossing_threshold(self):
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 1),
            start_time=time(10, 0),
            duration_minutes=120,
            status="taught",
        )
        third_lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 2),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.assertEqual(calculate_lesson_amount(third_lesson, self.tutor), Decimal("12.00"))

    def test_flat_rate_used_for_institute_without_tiers(self):
        plain_institute = Institute.objects.create(
            user=self.tutor, institute_name="UnconfiguredInstitute"
        )
        contract = Contract.objects.create(
            user=self.tutor,
            first_name="B",
            last_name="S",
            institute_fk=plain_institute,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )
        lesson = Lesson.objects.create(
            contract=contract,
            date=date(2025, 1, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.assertEqual(calculate_lesson_amount(lesson, self.tutor), Decimal("25.00"))

    def test_flat_rate_used_for_private_contract(self):
        contract = Contract.objects.create(
            user=self.tutor,
            first_name="C",
            last_name="S",
            institute_fk=None,
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )
        lesson = Lesson.objects.create(
            contract=contract,
            date=date(2025, 1, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.assertEqual(calculate_lesson_amount(lesson, self.tutor), Decimal("30.00"))

    def test_no_show_unpaid_flag_zeroes_amount_for_generic_institute(self):
        self.institute.tiers = []
        self.institute.unpaid_on_tutor_no_show = True
        self.institute.save(update_fields=["tiers", "unpaid_on_tutor_no_show"])
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        self.assertEqual(calculate_lesson_amount(lesson, self.tutor), Decimal("0.00"))
