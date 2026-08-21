"""
Regression tests for two UI fixes:

1. The week-view "jump to date" field no longer fires two conflicting
   'change' handlers (an inline onchange plus a separate addEventListener)
   that could navigate away before the year was fully typed - it now uses a
   single debounced handler.
2. The blocked-time form gained a "Ganzer Tag" (whole day) toggle that pins
   the start/end time to 00:00/23:59, so multi-day spans fully block every
   day in between.

These are frontend behaviors (debounce timing, checkbox JS), so the tests
here only assert the rendered markup/script contains the expected fix -
real interaction is exercised manually/by the browser, not by Django's test
client.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone


class WeekViewDateJumpTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = User.objects.create_user(username="tutor", password="test")
        self.client.force_login(self.tutor)

    def test_date_input_has_single_debounced_handler_not_double_onchange(self):
        """Regression: the date input must not carry a redundant inline
        onchange alongside the JS listener - that caused navigation before
        the year was fully typed."""
        response = self.client.get(reverse("lessons:week"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="date-select"', content)
        # Isolate the date input's own tag - a page-wide onchange check would
        # also match the unrelated language <select> in base.html.
        date_input_start = content.index('id="date-select"')
        date_input_tag = content[date_input_start - 200 : date_input_start + 200]
        self.assertNotIn("onchange=", date_input_tag)
        self.assertIn("DEBOUNCE_MS", content)
        self.assertIn("addEventListener('input'", content)
        self.assertIn("e.key === 'Enter'", content)


class BlockedTimeWholeDayToggleTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = User.objects.create_user(username="tutor", password="test")
        self.client.force_login(self.tutor)

    def test_create_form_has_whole_day_toggle(self):
        response = self.client.get(reverse("blocked_times:create"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="whole-day-toggle"', content)
        self.assertIn("applyWholeDay", content)
        self.assertIn("00:00", content)
        self.assertIn("23:59", content)

    def test_whole_day_span_creates_a_single_continuous_blocked_time(self):
        """A whole-day, multi-day blocked time is one continuous
        start/end range - every day in between is implicitly fully blocked
        without needing separate per-day records."""
        from apps.blocked_times.models import BlockedTime

        start_date = timezone.localdate() + timedelta(days=7)
        end_date = start_date + timedelta(days=2)

        response = self.client.post(
            reverse("blocked_times:create"),
            {
                "title": "Urlaub",
                "description": "",
                "start_datetime": start_date.strftime("%Y-%m-%dT00:00"),
                "end_datetime": end_date.strftime("%Y-%m-%dT23:59"),
            },
        )
        self.assertEqual(response.status_code, 302)
        bt = BlockedTime.objects.get(title="Urlaub")
        local_start = timezone.localtime(bt.start_datetime)
        local_end = timezone.localtime(bt.end_datetime)
        self.assertEqual(local_start.date(), start_date)
        self.assertEqual(local_end.date(), end_date)
        self.assertEqual(local_start.time().strftime("%H:%M"), "00:00")
        self.assertEqual(local_end.time().strftime("%H:%M"), "23:59")
