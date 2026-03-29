from datetime import date, time, timedelta
from decimal import Decimal

from apps.contracts.institute_utils import TUTORSPACE_INSTITUTE_NAME
from apps.contracts.models import Contract
from apps.contracts.tutorspace_compensation import (
    _tutorspace_minutes_before_session,
    calculate_tutorspace_amount_for_session,
    tutorspace_rate_for_hour_index,
)
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import TestCase


class TutorSpaceCompensationTierTest(TestCase):
    def test_tier_mapping_by_hour_index(self):
        self.assertEqual(tutorspace_rate_for_hour_index(1), Decimal("13"))
        self.assertEqual(tutorspace_rate_for_hour_index(50), Decimal("13"))
        self.assertEqual(tutorspace_rate_for_hour_index(51), Decimal("14"))
        self.assertEqual(tutorspace_rate_for_hour_index(150), Decimal("14"))
        self.assertEqual(tutorspace_rate_for_hour_index(151), Decimal("15"))
        self.assertEqual(tutorspace_rate_for_hour_index(450), Decimal("15"))
        self.assertEqual(tutorspace_rate_for_hour_index(451), Decimal("16"))
        self.assertEqual(tutorspace_rate_for_hour_index(1000), Decimal("16"))
        self.assertEqual(tutorspace_rate_for_hour_index(1001), Decimal("17"))


class TutorSpaceCompensationCumulativeTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_ts", password="x")
        s1 = Student.objects.create(user=self.tutor, first_name="A", last_name="S")
        s2 = Student.objects.create(user=self.tutor, first_name="B", last_name="S")
        self.c1 = Contract.objects.create(
            student=s1,
            institute=TUTORSPACE_INSTITUTE_NAME,
            hourly_rate=Decimal("13.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )
        self.c2 = Contract.objects.create(
            student=s2,
            institute=TUTORSPACE_INSTITUTE_NAME,
            hourly_rate=Decimal("13.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            is_active=True,
        )

    def test_cross_contract_cumulative_rate_increases_at_51st_hour(self):
        """
        Build 50h taught across two TutorSpace contracts (two pupils), then verify that the next
        (51st) hour is paid at 14€/h (global pool across all TutorSpace pupils).
        """
        start_day = date(2025, 1, 1)
        # 50 sessions * 60 minutes (25 per contract)
        for i in range(50):
            contract = self.c1 if i % 2 == 0 else self.c2
            Lesson.objects.create(
                contract=contract,
                date=start_day + timedelta(days=i),
                start_time=time(10, 0),
                duration_minutes=60,
                status="taught",
            )

        lesson_51 = Lesson.objects.create(
            contract=self.c1,
            date=start_day + timedelta(days=60),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        amount = calculate_tutorspace_amount_for_session(lesson_51, tutor=self.tutor)
        self.assertEqual(amount, Decimal("14.00"))

    def test_same_date_time_breaks_tie_by_created_at(self):
        """Same date & start_time: earlier created_at counts first in cumulative minutes."""
        d = date(2025, 3, 16)
        first = Lesson.objects.create(
            contract=self.c1,
            date=d,
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        second = Lesson.objects.create(
            contract=self.c2,
            date=d,
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertLess(first.created_at, second.created_at)
        self.assertEqual(_tutorspace_minutes_before_session(first, self.tutor), 0)
        self.assertEqual(_tutorspace_minutes_before_session(second, self.tutor), 60)

    def test_tutor_no_show_zero_percent_full_deduction(self):
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"tutor_no_show_pay_percent": 0}
        )
        lesson = Lesson.objects.create(
            contract=self.c1,
            date=date(2025, 2, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        amount = calculate_tutorspace_amount_for_session(lesson, tutor=self.tutor)
        self.assertEqual(amount, Decimal("-13.00"))

    def test_tutor_no_show_half_retention_halves_deduction(self):
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"tutor_no_show_pay_percent": 50}
        )
        lesson = Lesson.objects.create(
            contract=self.c1,
            date=date(2025, 2, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        amount = calculate_tutorspace_amount_for_session(lesson, tutor=self.tutor)
        self.assertEqual(amount, Decimal("-6.50"))

    def test_tutor_no_show_hundred_percent_full_pay(self):
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"tutor_no_show_pay_percent": 100}
        )
        lesson = Lesson.objects.create(
            contract=self.c1,
            date=date(2025, 2, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        amount = calculate_tutorspace_amount_for_session(lesson, tutor=self.tutor)
        self.assertEqual(amount, Decimal("13.00"))

    def test_tutor_no_show_minutes_do_not_advance_tier(self):
        """A no-show session must not count toward cumulative hours for later tiers."""
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"tutor_no_show_pay_percent": 0}
        )
        start_day = date(2025, 1, 1)
        for i in range(49):
            Lesson.objects.create(
                contract=self.c1,
                date=start_day + timedelta(days=i),
                start_time=time(10, 0),
                duration_minutes=60,
                status="taught",
                tutor_no_show=False,
            )
        Lesson.objects.create(
            contract=self.c1,
            date=start_day + timedelta(days=49),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
            tutor_no_show=True,
        )
        next_lesson = Lesson.objects.create(
            contract=self.c1,
            date=start_day + timedelta(days=50),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        amount = calculate_tutorspace_amount_for_session(next_lesson, tutor=self.tutor)
        self.assertEqual(amount, Decimal("13.00"))
