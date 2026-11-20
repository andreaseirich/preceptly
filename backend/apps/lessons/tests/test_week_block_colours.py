"""Wochenansicht: Zustand und Farbe der Unterrichtsblöcke kommen aus Klassen und Design-Tokens, nicht aus festen Farbwerten im Inline-Stil.

Vorher: feste Farben (#ff9800 mit weißer Schrift = 2,2:1, #607d8b mit Weiß = 4,0:1, Gelb auf Türkis) und weiße Schrift auf der Akzentfarbe, die
im dunklen Thema hell ist. Jetzt hängt die Farbe an `lesson-block--planned|taught|paid` und an den Tokens; der Kontrast der Tokens
prüft test_design_tokens.
"""

import re
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson


class WeekViewBlocksTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("tutor_woche", password="pw")
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Emil",
            last_name="Beispiel",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        self.client.force_login(self.tutor)
        # Vergangene geplante Stunden zählen als gehalten: darum die kommende Woche nehmen
        today = timezone.localdate()
        self.monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    def lesson(self, day_offset, hour, status):
        return Lesson.objects.create(
            contract=self.contract,
            date=self.monday + timedelta(days=day_offset),
            start_time=time(hour, 0),
            duration_minutes=60,
            status=status,
        )

    def week(self):
        response = self.client.get(
            reverse("lessons:week"),
            {"year": self.monday.year, "month": self.monday.month, "day": self.monday.day},
        )
        return response.content.decode()

    @staticmethod
    def classes_of(html, lesson):
        """Die Klassen des Blocks dieser Stunde. Nur so zählt es: Die Klassennamen stehen auch im CSS der Seite."""
        match = re.search(rf'class="([^"]*)"\s+data-lesson-id="{lesson.pk}"', html)
        assert match, f"Block der Stunde {lesson.pk} nicht gefunden"
        return match.group(1).split()

    def week_without_scripts(self):
        """Die Tooltips baut JavaScript als dunkle Blase in beiden Themen; geprüft wird das HTML der Blöcke."""
        return re.sub(r"<script\b.*?</script>", "", self.week(), flags=re.S)

    def test_each_status_gets_its_own_class(self):
        lessons = {
            status: self.lesson(day, 10 + day, status)
            for day, status in enumerate(("planned", "taught", "paid"))
        }
        html = self.week()

        for status, lesson in lessons.items():
            with self.subTest(status=status):
                classes = self.classes_of(html, lesson)
                self.assertIn(f"lesson-block--{status}", classes)
                for other in {"planned", "taught", "paid"} - {status}:
                    self.assertNotIn(f"lesson-block--{other}", classes)

    def test_block_colours_are_not_hard_coded_any_more(self):
        self.lesson(0, 10, "paid")
        self.lesson(1, 11, "taught")
        start = timezone.make_aware(
            timezone.datetime.combine(self.monday + timedelta(days=3), time(9, 0))
        )
        BlockedTime.objects.create(
            user=self.tutor,
            title="Vorlesung",
            start_datetime=start,
            end_datetime=start + timedelta(hours=2),
        )
        html = self.week_without_scripts()

        for old in ("#ff9800", "#2e7d32", "#607d8b", "#ffeb3b", "rgba(33, 150, 243"):
            with self.subTest(farbe=old):
                self.assertNotIn(old, html)

    def test_a_conflict_is_marked_with_the_danger_token(self):
        first = self.lesson(0, 10, "planned")
        self.lesson(0, 10, "planned")
        html = self.week()

        self.assertIn("has-conflict", self.classes_of(html, first))
        self.assertIn("lesson-conflict-flag", html)
        self.assertIn("border: 2px solid var(--danger)", html)

    def test_blocked_times_have_their_own_class_and_no_fixed_colour(self):
        start = timezone.make_aware(
            timezone.datetime.combine(self.monday + timedelta(days=2), time(9, 0))
        )
        BlockedTime.objects.create(
            user=self.tutor,
            title="Vorlesung",
            start_datetime=start,
            end_datetime=start + timedelta(hours=2),
        )
        html = self.week()

        self.assertIn("blocked-time-block", html)
        self.assertIn(".blocked-time-block { background: color-mix(", html)

    def test_the_edit_link_inside_a_block_is_a_named_control(self):
        self.lesson(0, 10, "planned")

        self.assertIn('class="lesson-edit"', self.week())
