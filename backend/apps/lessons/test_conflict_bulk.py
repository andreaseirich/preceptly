"""check_conflicts_bulk muss für jede Stunde exakt dasselbe liefern wie
check_conflicts - nur mit wenigen Abfragen statt vier pro Stunde."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.lessons.models import Lesson
from apps.lessons.services import LessonConflictService


def _summary(conflicts):
    return [(c["type"], c["object"].pk, c["message"]) for c in conflicts]


class ConflictBulkTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("lehrer", password="pw")
        self.day = date.today() + timedelta(days=3)
        # Vertrag mit Kontingent: 1 Einheit in diesem Monat, 3 Stunden geplant
        self.limited = self._contract(self.user, limit=True)
        ContractMonthlyPlan.objects.create(
            contract=self.limited, year=self.day.year, month=self.day.month, planned_units=1
        )
        self.free = self._contract(self.user, limit=False)
        self._lesson(self.limited, time(14, 0))
        self._lesson(self.free, time(14, 30))  # überlappt die 14-Uhr-Stunde
        self._lesson(self.limited, time(9, 0), travel_after=30)
        self._lesson(self.free, time(9, 45))  # überlappt nur durch die Fahrtzeit
        self._lesson(self.limited, time(18, 0))
        BlockedTime.objects.create(
            user=self.user,
            title="Uni",
            start_datetime=timezone.make_aware(datetime.combine(self.day, time(17, 30))),
            end_datetime=timezone.make_aware(datetime.combine(self.day, time(18, 30))),
        )
        # Ein anderer Tutor zur gleichen Zeit darf nie zählen
        other = User.objects.create_user("andere", password="pw")
        self._lesson(self._contract(other, limit=False), time(14, 0))

    def _contract(self, user, limit):
        return Contract.objects.create(
            user=user,
            first_name="S",
            last_name=user.username,
            hourly_rate=Decimal("25"),
            unit_duration_minutes=60,
            start_date=self.day.replace(day=1),
            has_monthly_planning_limit=limit,
        )

    def _lesson(self, contract, start, travel_after=0):
        return Lesson.objects.create(
            contract=contract,
            date=self.day,
            start_time=start,
            duration_minutes=60,
            travel_time_after_minutes=travel_after,
            status="planned",
        )

    def _mine(self):
        return list(Lesson.objects.filter(contract__user=self.user))

    def test_same_result_as_one_by_one(self):
        bulk = LessonConflictService.check_conflicts_bulk(self._mine())

        for lesson in self._mine():
            with self.subTest(stunde=f"{lesson.start_time}"):
                single = LessonConflictService.check_conflicts(Lesson.objects.get(pk=lesson.pk))
                self.assertEqual(_summary(bulk[lesson.pk]), _summary(single))
        found = {c["type"] for conflicts in bulk.values() for c in conflicts}
        self.assertEqual(found, {"lesson", "blocked_time", "quota"})

    def test_same_result_without_excluding_self(self):
        bulk = LessonConflictService.check_conflicts_bulk(self._mine(), exclude_self=False)

        for lesson in self._mine():
            with self.subTest(stunde=f"{lesson.start_time}"):
                single = LessonConflictService.check_conflicts(
                    Lesson.objects.get(pk=lesson.pk), exclude_self=False
                )
                self.assertEqual(_summary(bulk[lesson.pk]), _summary(single))

    def test_number_of_queries_does_not_grow_with_lessons(self):
        with CaptureQueriesContext(connection) as few:
            LessonConflictService.check_conflicts_bulk(self._mine())
        for hour in range(10, 14):
            self._lesson(self.free, time(hour, 0))
        with CaptureQueriesContext(connection) as many:
            LessonConflictService.check_conflicts_bulk(self._mine())

        self.assertEqual(len(many.captured_queries), len(few.captured_queries))

    def test_empty_list(self):
        self.assertEqual(LessonConflictService.check_conflicts_bulk([]), {})
