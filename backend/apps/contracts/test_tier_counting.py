"""Stufenvergütung: Zählweise je Institut und Startwert.

Anlass 02.10.2026: TutorSpace zählt jede angefangene Stunde eines Termins als
eine Einheit. Preceptly zählte Minuten und lag hinter dem Zähler des Instituts."""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.contracts.institute_billing import calculate_lesson_amount
from apps.contracts.models import Contract, Institute
from apps.contracts.services import get_institute_tier_progress
from apps.contracts.tier_counting import (
    COUNT_BY_DURATION,
    COUNT_BY_STARTED_HOUR,
    counted_total,
    started_hours,
)
from apps.lessons.models import Lesson

TIERS = [
    {"hours_from": 0, "rate": 14, "label": "14 €/h"},
    {"hours_from": 3, "rate": 15, "label": "15 €/h"},
]


class TierCountingFixture(TestCase):
    mode = COUNT_BY_STARTED_HOUR
    offset = 0

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_units", password="x")
        self.institute = Institute.objects.create(
            user=self.tutor,
            institute_name="Einheiten-Institut",
            tiers=TIERS,
            tier_count_mode=self.mode,
            tier_count_offset=self.offset,
        )
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="A",
            last_name="S",
            institute_fk=self.institute,
            hourly_rate=Decimal("14.00"),
            unit_duration_minutes=60,
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        self._day = date(2026, 9, 1)

    def lesson(self, minutes, **extra):
        self._day += timedelta(days=1)
        return Lesson.objects.create(
            contract=self.contract,
            date=self._day,
            start_time=time(16, 0),
            duration_minutes=minutes,
            status="taught",
            **extra,
        )

    def amount(self, lesson):
        return calculate_lesson_amount(lesson, self.tutor)


class StartedHoursTest(TestCase):
    def test_every_started_hour_counts_as_one(self):
        self.assertEqual([started_hours(m) for m in (30, 60, 61, 90, 120)], [1, 1, 2, 2, 2])

    def test_counter_by_mode(self):
        durations = [30, 30, 60, 120]

        self.assertEqual(counted_total(durations, COUNT_BY_DURATION), Decimal("4"))
        self.assertEqual(counted_total(durations, COUNT_BY_STARTED_HOUR), Decimal("5"))
        self.assertEqual(counted_total(durations, COUNT_BY_STARTED_HOUR, offset=5), Decimal("10"))


class CountByUnitTest(TierCountingFixture):
    def test_short_lessons_count_fully_but_pay_by_duration(self):
        first = self.lesson(30)
        self.lesson(30)
        self.lesson(30)
        fourth = self.lesson(60)
        half = self.lesson(30)

        self.assertEqual(self.amount(first), Decimal("7.00"))
        # drei Einheiten sind voll, obwohl erst 90 Minuten unterrichtet wurden
        self.assertEqual(self.amount(fourth), Decimal("15.00"))
        self.assertEqual(self.amount(half), Decimal("7.50"))

    def test_long_lesson_across_the_threshold_pays_each_hour_at_its_rate(self):
        self.lesson(60)
        self.lesson(60)
        double = self.lesson(120)  # Einheit 3 zu 14 €, Einheit 4 zu 15 €

        self.assertEqual(self.amount(double), Decimal("29.00"))

    def test_tutor_no_show_lessons_do_not_count(self):
        self.lesson(60)
        self.lesson(60)
        self.lesson(60, tutor_no_show=True)
        fourth = self.lesson(60)

        self.assertEqual(self.amount(fourth), Decimal("14.00"))

    def test_progress_shows_units(self):
        for minutes in (30, 30, 120):
            self.lesson(minutes)

        progress = get_institute_tier_progress(self.institute)

        self.assertEqual(progress["total_hours"], 4)
        self.assertEqual(progress["current_tier_label"], "15 €/h")
        self.assertIn(progress["unit_label"], ("units", "Einheiten"))


class StartValueTest(TierCountingFixture):
    offset = 2

    def test_start_value_moves_the_threshold(self):
        first = self.lesson(60)  # Einheit 3
        second = self.lesson(60)  # Einheit 4

        self.assertEqual(self.amount(first), Decimal("14.00"))
        self.assertEqual(self.amount(second), Decimal("15.00"))
        self.assertEqual(get_institute_tier_progress(self.institute)["total_hours"], 4)


class CountByDurationTest(TierCountingFixture):
    mode = COUNT_BY_DURATION

    def test_default_still_counts_minutes(self):
        self.lesson(30)
        self.lesson(30)
        self.lesson(30)
        fourth = self.lesson(60)  # beginnt bei 1,5 Stunden

        self.assertEqual(Institute._meta.get_field("tier_count_mode").default, COUNT_BY_DURATION)
        self.assertEqual(self.amount(fourth), Decimal("14.00"))
        progress = get_institute_tier_progress(self.institute)
        self.assertEqual(progress["total_hours"], 2.5)
        self.assertEqual(progress["unit_label"], "h")

    def test_start_value_counts_as_hours(self):
        self.institute.tier_count_offset = 3
        self.institute.save()

        self.assertEqual(self.amount(self.lesson(60)), Decimal("15.00"))


class InstituteFormTest(TierCountingFixture):
    mode = COUNT_BY_DURATION

    def test_tutor_can_switch_the_counting_and_set_a_start_value(self):
        self.client.force_login(self.tutor)
        url = reverse("contracts:institute_update", args=[self.institute.pk])

        page = self.client.get(url)
        self.assertContains(page, 'name="tier_count_mode"')
        self.assertContains(page, 'name="tier_count_offset"')

        import json

        self.client.post(
            url,
            {
                "institute_name": self.institute.institute_name,
                "tiers": json.dumps(TIERS),
                "tutor_no_show_pay_percent": 0,
                "tier_count_mode": COUNT_BY_STARTED_HOUR,
                "tier_count_offset": 5,
            },
        )
        self.institute.refresh_from_db()

        self.assertEqual(self.institute.tier_count_mode, COUNT_BY_STARTED_HOUR)
        self.assertEqual(self.institute.tier_count_offset, 5)

    def test_invoice_preview_explains_units(self):
        self.institute.tier_count_mode = COUNT_BY_STARTED_HOUR
        self.institute.tier_count_offset = 5
        self.institute.save()
        self.lesson(30)
        billed = self.lesson(60)
        self.client.force_login(self.tutor)

        page = self.client.get(
            reverse("billing:invoice_create"),
            {
                "period_start": billed.date.isoformat(),
                "period_end": billed.date.isoformat(),
                "institute": self.institute.pk,
            },
        )

        self.assertContains(page, "<strong>6</strong> Einheiten")
