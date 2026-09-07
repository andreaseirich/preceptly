"""
Regression test: a multi-hour BlockedTime (or another student's
multi-hour session) must show "Belegt"/be included in every hourly row
it spans on the portal week calendar widget, not just its starting
hour. Reported live: a block from 18:45-20:00 only showed as occupied
at 18:00, leaving 19:00 looking free even though booking it was
actually still rejected server-side.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.lessons.models import Session
from apps.portal.models import ParentStudentLink, PortalUser
from apps.portal.views import _build_week_calendar


class WeekCalendarMultiHourBlockedTimeTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_wk", password="pass")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Max",
            last_name="Muster",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        self.portal_django_user = User.objects.create_user(username="parent_wk", password="pass")
        self.portal_user = PortalUser.objects.create(
            user=self.portal_django_user, role="parent", tutor=self.tutor
        )
        ParentStudentLink.objects.create(
            parent=self.portal_user, contract=self.contract, is_active=True
        )

    def _next_monday(self):
        today = timezone.localdate()
        return today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    def test_multi_hour_blocked_time_covers_every_spanned_hour(self):
        monday = self._next_monday()
        start = timezone.make_aware(datetime.combine(monday, time(18, 45)))
        end = timezone.make_aware(datetime.combine(monday, time(20, 0)))
        BlockedTime.objects.create(
            user=self.tutor, title="Jugendchor", start_datetime=start, end_datetime=end
        )

        result = _build_week_calendar(self.contract, monday.year, monday.month, monday.day)
        weekday = next(w for w in result["weekdays"] if w["date"] == monday)
        hours_seen = set()
        for slot in weekday["busy"]:
            hours_seen.update(slot["hours_covered"])

        self.assertIn(18, hours_seen)
        self.assertIn(19, hours_seen, "19:00 must be covered by an 18:45-20:00 block")
        self.assertNotIn(20, hours_seen, "block ends at 20:00, so 20:00 itself is free")

    def test_other_students_multi_hour_session_covers_every_spanned_hour(self):
        other_contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lena",
            last_name="Beispiel",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        monday = self._next_monday()
        Session.objects.create(
            contract=other_contract, date=monday, start_time=time(18, 0), duration_minutes=120
        )

        result = _build_week_calendar(self.contract, monday.year, monday.month, monday.day)
        weekday = next(w for w in result["weekdays"] if w["date"] == monday)
        hours_seen = set()
        for slot in weekday["busy"]:
            hours_seen.update(slot["hours_covered"])

        self.assertEqual(hours_seen, {18, 19})

    def test_booking_page_html_shows_belegt_for_middle_hour(self):
        monday = self._next_monday()
        start = timezone.make_aware(datetime.combine(monday, time(18, 45)))
        end = timezone.make_aware(datetime.combine(monday, time(20, 0)))
        BlockedTime.objects.create(
            user=self.tutor, title="Jugendchor", start_datetime=start, end_datetime=end
        )

        client = Client()
        session = client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

        response = client.get(
            reverse("portal:book", args=[self.contract.pk]),
            {"year": monday.year, "month": monday.month, "day": monday.day},
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # Rough check: the "19:00" row's <tr> block must contain "Belegt".
        idx = body.find(">19:00<")
        self.assertNotEqual(idx, -1)
        next_tr = body.find("</tr>", idx)
        self.assertIn("Belegt", body[idx:next_tr])
