"""Dashboard: "Heute" und "Anstehend" gelten für das deutsche Datum, auch kurz nach Mitternacht.

Gefunden am 20.11.2026 um 00:15 Uhr deutscher Zeit: Ein Test fiel um, weil `SessionQueryService` das UTC-Datum nahm
(`timezone.now().date()`). Zwischen 00:00 und 01:00 Uhr (im Sommer bis 02:00) liegt UTC einen Tag zurück: Das Dashboard hielt
"heute" für gestern, zeigte dort die Stunden von gestern und verschob das Fenster der kommenden sieben Tage.
"""

from datetime import date, datetime, time
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from apps.lessons.query_service import SessionQueryService

# 23:30 Uhr UTC am 19.11.2026 ist 00:30 Uhr am 20.11.2026 in Berlin
NIGHT = datetime(2026, 11, 19, 23, 30, tzinfo=dt_timezone.utc)


class DashboardAfterMidnightTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("nacht_tutor", password="pw", email="n@example.com")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Nora",
            last_name="Nacht",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2026, 1, 1),
        )

    def lesson(self, day):
        return Lesson.objects.create(
            contract=self.contract,
            date=day,
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

    def test_today_is_the_german_date_not_the_utc_date(self):
        yesterday = self.lesson(date(2026, 11, 19))
        today = self.lesson(date(2026, 11, 20))

        with mock.patch("django.utils.timezone.now", return_value=NIGHT):
            shown = list(SessionQueryService.get_today_sessions(user=self.tutor))

        self.assertEqual(shown, [today], "um 00:30 Uhr am 20.11. ist heute der 20.11.")
        self.assertNotIn(yesterday, shown)

    def test_the_next_seven_days_start_tomorrow_german_time(self):
        today = self.lesson(date(2026, 11, 20))
        tomorrow = self.lesson(date(2026, 11, 21))
        last_day = self.lesson(date(2026, 11, 27))
        too_late = self.lesson(date(2026, 11, 28))

        with mock.patch("django.utils.timezone.now", return_value=NIGHT):
            shown = list(SessionQueryService.get_upcoming_sessions(days=7, user=self.tutor))

        self.assertEqual(shown, [tomorrow, last_day])
        self.assertNotIn(today, shown, "heute steht im Abschnitt Heute")
        self.assertNotIn(too_late, shown)

    def test_during_the_day_both_dates_agree(self):
        noon = datetime(2026, 11, 20, 11, 0, tzinfo=dt_timezone.utc)  # 12:00 Uhr in Berlin
        today = self.lesson(date(2026, 11, 20))

        with mock.patch("django.utils.timezone.now", return_value=noon):
            shown = list(SessionQueryService.get_today_sessions(user=self.tutor))

        self.assertEqual(shown, [today])
