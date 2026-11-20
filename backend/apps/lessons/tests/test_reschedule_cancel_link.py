"""Stunde verschieben: „Abbrechen“ führt zurück.

Befund vom 20.11.2026: Der Link hatte `href="{{ request.GET.next|default:'javascript:history.back()' }}"`. Die Inhaltssicherheitsrichtlinie (CSP) blockiert
javascript:-Adressen, ohne `?next=` tat „Abbrechen“ also nichts. Mit `?next=` landete eine beliebige Adresse aus der Adresszeile im Link. Jetzt gibt es
`data-history-back` (eine Seite zurück, siehe actions.js) mit der Stunde als echtem Rückfall-Link.
"""

import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson


class RescheduleCancelLinkTest(TestCase):
    def setUp(self):
        # mit E-Mail-Adresse: Ohne sie zeigt jede Seite einen Banner, dessen Link die aktuelle Adresse als ?next= trägt (dort prüft der Server das Ziel)
        self.tutor = User.objects.create_user(
            "tutor_verschieben", password="pw", email="tutor.verschieben@example.com"
        )
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        today = timezone.localdate()
        contract = Contract.objects.create(
            user=self.tutor,
            first_name="Ida",
            last_name="Beispiel",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=today - timedelta(days=30),
        )
        self.lesson = Lesson.objects.create(
            contract=contract,
            date=today + timedelta(days=3),
            start_time="15:00",
            duration_minutes=60,
        )
        self.client.force_login(self.tutor)
        self.url = reverse("lessons:reschedule", args=[self.lesson.pk])

    def test_the_page_contains_no_javascript_address(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "javascript:")

    def test_cancel_goes_back_in_history_and_falls_back_to_the_lesson(self):
        html = self.client.get(self.url).content.decode()
        detail = reverse("lessons:detail", args=[self.lesson.pk])

        self.assertRegex(
            html, rf'<a href="{re.escape(detail)}"[^>]*data-history-back[^>]*>Abbrechen</a>'
        )

    def test_an_address_from_the_query_string_is_not_used_as_a_link(self):
        """Im versteckten Feld der Sprachwahl steht die aktuelle Adresse (Django prüft dort selbst das Ziel); in einem Link darf sie nicht stehen."""
        html = self.client.get(
            self.url, {"next": "https://boese.example/phishing"}
        ).content.decode()

        self.assertNotRegex(html, r'href="[^"]*boese\.example')
