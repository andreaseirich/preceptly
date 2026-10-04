"""Die beiden FAQ-Seiten: öffentlich für Tutoren, im Portal für Familien.

Beide wurden am 02.10.2026 stark erweitert. Die Tests sichern, dass jede Seite
lädt, dass alle Sprunglinks ein Ziel haben und dass Angaben, die sich aus dem
Code ergeben, mit ihm übereinstimmen."""

import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.feature_flags import (
    FREE_INVOICE_MONTHLY_LIMIT,
    FREE_STUDENT_LIMIT,
    STARTER_DOCUMENT_LIMIT,
    STARTER_PORTAL_BOOKING_MONTHLY_LIMIT,
)
from apps.portal.models import PortalUser


def _anchors_without_target(html):
    targets = set(re.findall(r'\bid="([^"]+)"', html))
    links = set(re.findall(r'href="#([a-z0-9-]+)"', html))
    return sorted(links - targets)


class TutorFaqTest(TestCase):
    def setUp(self):
        self.response = self.client.get(reverse("core:faq"))
        self.html = self.response.content.decode()

    def test_public_without_login(self):
        self.assertEqual(self.response.status_code, 200)

    def test_every_jump_link_has_a_target(self):
        self.assertIn('href="#tarife"', self.html)
        self.assertEqual(_anchors_without_target(self.html), [])

    def test_template_comments_are_not_rendered(self):
        # Django kennt {# #} nur einzeilig; ein mehrzeiliger Kommentar erschien als Text.
        self.assertNotIn("{#", self.html)

    def test_menu_lists_every_topic_and_every_menu_link_has_a_section(self):
        page = re.escape(reverse("core:faq"))
        # ohne den Skip-Link „Zum Inhalt springen“ aus base.html
        topics = set(re.findall(r'href="#([a-z0-9-]+)"', self.html)) - {"main-content"}
        menu = set(re.findall(rf'href="{page}#([a-z0-9-]+)"', self.html))
        sections = set(re.findall(r'\bid="([a-z0-9-]+)"', self.html))

        self.assertEqual(sorted(topics - menu), [])
        self.assertEqual(sorted(menu - sections), [])

    def test_nav_dropdown_targets_still_exist(self):
        for anchor in (
            "einnahmen",
            "rechnungen",
            "stunden",
            "steuern",
            "berichte",
            "gestaffelte-verguetung",
        ):
            with self.subTest(anchor=anchor):
                self.assertIn(f'id="{anchor}"', self.html)

    def test_limits_match_the_code(self):
        self.assertIn(f"Dokumente ({STARTER_DOCUMENT_LIMIT} je Schüler)", self.html)
        self.assertIn(f"bis zu {STARTER_PORTAL_BOOKING_MONTHLY_LIMIT} Portal-Buchungen", self.html)
        self.assertIn(
            f"Ab {FREE_STUDENT_LIMIT} Schülern und ab {FREE_INVOICE_MONTHLY_LIMIT} Rechnungen",
            self.html,
        )

    def test_explains_that_portal_series_leave_out_busy_days(self):
        self.assertIn("lässt das Portal aus", self.html)

    def test_no_outdated_claim_about_deleting_sent_invoices(self):
        self.assertIn("Ändern und löschen kannst du nur Entwürfe", self.html)


class PortalFaqTest(TestCase):
    def setUp(self):
        tutor = User.objects.create_user(username="tutor_faq", password="x")
        account = PortalUser.objects.create(
            user=User.objects.create_user(username="portal_faq", password="x"),
            role="student",
            tutor=tutor,
        )
        session = self.client.session
        session["portal_user_id"] = account.pk
        session.save()
        self.html = self.client.get(reverse("portal:faq")).content.decode()

    def test_requires_portal_login(self):
        session = self.client.session
        del session["portal_user_id"]
        session.save()

        self.assertRedirects(self.client.get(reverse("portal:faq")), reverse("portal:login"))

    def test_every_jump_link_has_a_target(self):
        self.assertIn('href="#buchen"', self.html)
        self.assertEqual(_anchors_without_target(self.html), [])

    def test_template_comments_are_not_rendered(self):
        self.assertNotIn("{#", self.html)

    def test_explains_that_series_leave_out_busy_days(self):
        self.assertIn("wird dieser Tag ausgelassen", self.html)

    def test_explains_automatic_status_and_what_happens_on_cancelling(self):
        self.assertIn("wechselt automatisch auf „Unterrichtet“", self.html)
        self.assertIn("steht er danach bei „Abgesagte Termine“", self.html)
        self.assertIn("Er bekommt eine Benachrichtigung", self.html)
