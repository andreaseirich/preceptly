from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.institute_billing import (
    calculate_lesson_amount,
    resolve_institute_billing_config,
)
from apps.contracts.models import Contract, InstituteTierConfig
from apps.contracts.tutorspace_compensation import calculate_tutorspace_amount_for_session
from apps.lessons.models import Lesson


class ResolveInstituteBillingConfigTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_ib", password="x")

    def test_no_institute_returns_none(self):
        self.assertIsNone(resolve_institute_billing_config(self.tutor, ""))
        self.assertIsNone(resolve_institute_billing_config(self.tutor, None))

    def test_unknown_institute_without_config_returns_none(self):
        self.assertIsNone(resolve_institute_billing_config(self.tutor, "SomeOtherSchool"))

    def test_tutorspace_without_config_uses_builtin_preset(self):
        config = resolve_institute_billing_config(self.tutor, "TutorSpace")
        self.assertIsNotNone(config)
        self.assertTrue(config.tiers)
        self.assertFalse(config.unpaid_on_tutor_no_show)

    def test_abacus_without_config_uses_builtin_no_show_rule(self):
        config = resolve_institute_billing_config(self.tutor, "Abacus")
        self.assertIsNotNone(config)
        self.assertIsNone(config.tiers)
        self.assertTrue(config.unpaid_on_tutor_no_show)

    def test_custom_institute_with_explicit_config(self):
        InstituteTierConfig.objects.create(
            user=self.tutor,
            institute_name="MyInstitute",
            tiers=[
                {"hours_from": 0, "rate": 10, "label": "10 €/h"},
                {"hours_from": 20, "rate": 12, "label": "12 €/h"},
            ],
            unpaid_on_tutor_no_show=True,
        )
        config = resolve_institute_billing_config(self.tutor, "MyInstitute")
        self.assertIsNotNone(config)
        self.assertEqual(len(config.tiers), 2)
        self.assertTrue(config.unpaid_on_tutor_no_show)

    def test_case_insensitive_institute_name_matching(self):
        InstituteTierConfig.objects.create(
            user=self.tutor,
            institute_name="MyInstitute",
            tiers=[{"hours_from": 0, "rate": 10, "label": "10 €/h"}],
        )
        config = resolve_institute_billing_config(self.tutor, "myinstitute")
        self.assertIsNotNone(config)
        self.assertTrue(config.tiers)

    def test_config_with_only_no_show_flag_and_no_tiers(self):
        InstituteTierConfig.objects.create(
            user=self.tutor,
            institute_name="NoShowOnlyInstitute",
            tiers=[],
            unpaid_on_tutor_no_show=True,
        )
        config = resolve_institute_billing_config(self.tutor, "NoShowOnlyInstitute")
        self.assertIsNotNone(config)
        self.assertIsNone(config.tiers)
        self.assertTrue(config.unpaid_on_tutor_no_show)

    def test_config_with_empty_tiers_and_no_flag_returns_none(self):
        InstituteTierConfig.objects.create(
            user=self.tutor,
            institute_name="PlainInstitute",
            tiers=[],
            unpaid_on_tutor_no_show=False,
        )
        config = resolve_institute_billing_config(self.tutor, "PlainInstitute")
        self.assertIsNone(config)


class CalculateLessonAmountGenericInstituteTest(TestCase):
    """Custom institutes should behave exactly like the InvoiceService's own tiered/no-show
    logic once a tutor configures an InstituteTierConfig for them."""

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_generic", password="x")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="A",
            last_name="S",
            institute="MyInstitute",
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )
        InstituteTierConfig.objects.create(
            user=self.tutor,
            institute_name="MyInstitute",
            tiers=[
                {"hours_from": 0, "rate": 10, "label": "10 €/h"},
                {"hours_from": 2, "rate": 12, "label": "12 €/h"},
            ],
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

    def test_flat_rate_used_for_institute_without_config(self):
        contract = Contract.objects.create(
            user=self.tutor,
            first_name="B",
            last_name="S",
            institute="UnconfiguredInstitute",
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

    def test_no_show_unpaid_flag_zeroes_amount_for_generic_institute(self):
        InstituteTierConfig.objects.filter(user=self.tutor, institute_name="MyInstitute").update(
            tiers=[], unpaid_on_tutor_no_show=True
        )
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        self.assertEqual(calculate_lesson_amount(lesson, self.tutor), Decimal("0.00"))


class TutorSpaceGenericPathMatchesLegacyTest(TestCase):
    """The generic calculate_lesson_amount() must reproduce calculate_tutorspace_amount_for_session()
    bit-for-bit for TutorSpace contracts without an explicit InstituteTierConfig override."""

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_parity", password="x")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="A",
            last_name="S",
            institute="TutorSpace",
            hourly_rate=Decimal("13.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )

    def test_generic_and_legacy_calculation_agree(self):
        lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 1, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        legacy_amount = calculate_tutorspace_amount_for_session(lesson, tutor=self.tutor)
        generic_amount = calculate_lesson_amount(lesson, self.tutor)
        self.assertEqual(legacy_amount, generic_amount)
        self.assertEqual(generic_amount, Decimal("13.00"))
