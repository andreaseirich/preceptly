"""Öffentliche Seiten: genau eine Hauptüberschrift, Beschriftungen an Feldern, und eine Startseite, die zum Code passt.

Die Startseite nennt Grenzen und Tarife. Diese Zahlen stehen im Code (feature_flags): Die Tests holen sie von dort, damit Seite und Verhalten
nicht auseinanderlaufen. Befund vom 20.11.2026: Die Grenzen des kostenlosen Tarifs (5 Schüler, 8 Rechnungen im Monat) wurden durchgesetzt,
standen aber nirgends; Funktionen trugen das Etikett „Premium“, obwohl es diesen Tarif nicht gibt.
"""

import re

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from apps.core.feature_flags import (
    FEATURE_MIN_TIER,
    FREE_INVOICE_MONTHLY_LIMIT,
    FREE_STUDENT_LIMIT,
    Feature,
    Tier,
)


def get_in(client, name, lang):
    """Seite in der gewählten Sprache holen: Die Sprachwahl der Seite setzt dieses Cookie."""
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
    return client.get(reverse(name))


PUBLIC_PAGES = [
    "core:landing",
    "core:faq",
    "core:login",
    "core:register",
    "core:password_reset",
    "core:legal_imprint",
    "core:legal_privacy",
    "core:legal_terms",
    "core:legal_avv",
    "core:legal_withdrawal",
    "core:legal_about",
    "portal:login",
    "portal:password_reset",
]


class OneMainHeadingTest(TestCase):
    def test_every_public_page_has_exactly_one_h1(self):
        for name in PUBLIC_PAGES:
            for lang in ("de", "en"):
                with self.subTest(seite=name, sprache=lang):
                    response = get_in(self.client, name, lang)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(len(re.findall(r"<h1\b", response.content.decode())), 1)


class LandingFactsTest(TestCase):
    def get(self, lang="de"):
        return get_in(self.client, "core:landing", lang)

    def test_the_limits_of_the_free_plan_are_named(self):
        de = self.get("de").content.decode()
        en = self.get("en").content.decode()

        # Wortlaut und Zählregeln prüft test_free_tier_wording; hier nur: Die Zahlen kommen aus den Konstanten
        self.assertIn(f"Gedacht für bis zu {FREE_STUDENT_LIMIT} Schülerverträge", de)
        self.assertIn(f"Gedacht für bis zu {FREE_INVOICE_MONTHLY_LIMIT} Rechnungen im Monat", de)
        self.assertIn(f"Intended for up to {FREE_STUDENT_LIMIT} student contracts", en)
        self.assertIn(f"Intended for up to {FREE_INVOICE_MONTHLY_LIMIT} invoices per month", en)

    def test_there_is_no_plan_called_premium(self):
        """Tarife heißen Free, Starter, Pro und Business; „Premium“ als Etikett an Funktionen führte in die Irre."""
        for lang in ("de", "en"):
            with self.subTest(sprache=lang):
                self.assertNotContains(self.get(lang), "lp-badge")
                self.assertNotContains(self.get(lang), ">Premium<")

    def test_prices_are_listed_for_all_paid_plans(self):
        html = self.get().content.decode()

        for price in ("4,99 €", "9,99 €", "19,99 €"):
            with self.subTest(preis=price):
                self.assertIn(price, html)

    def test_no_unsourced_time_saving_claim(self):
        """Die frühere Zahl „2–3 Stunden pro Woche“ hatte keine Quelle."""
        for lang in ("de", "en"):
            with self.subTest(sprache=lang):
                html = self.get(lang).content.decode()
                self.assertNotIn("2–3 Stunden", html)
                self.assertNotIn("2–3 hours", html)

    def test_pro_features_are_listed_under_the_pro_plan_not_under_starter(self):
        """Meetingräume und KI-Pläne brauchen mindestens Pro (feature_flags). Auf der Seite stehen sie nach der Pro-Überschrift."""
        self.assertEqual(FEATURE_MIN_TIER[Feature.FEATURE_MEETING_ROOMS], Tier.PRO)
        self.assertEqual(FEATURE_MIN_TIER[Feature.FEATURE_AI_LESSON_PLANS], Tier.PRO)
        html = self.get("en").content.decode()

        pro_start = html.index("Included from the Pro plan")
        self.assertGreater(html.index("Integrated Meeting Rooms"), pro_start)
        self.assertGreater(html.index("AI Lesson Plans"), pro_start)
        starter_start = html.index("Included from the Starter plan")
        self.assertGreater(html.index("Document Management"), starter_start)
        self.assertLess(html.index("Document Management"), pro_start)

    def test_the_page_has_a_single_pricing_anchor(self):
        self.assertEqual(self.get().content.decode().count('id="pricing"'), 1)

    def test_every_translatable_text_is_translated_into_german(self):
        """Kein englischer Rest in der deutschen Startseite."""
        html = self.get("de").content.decode()
        for fragment in (
            "Included in the free plan",
            "Does this sound familiar",
            "Get Started",
            "Sign Up for Free",
            "Start free",
            "Privacy built into",
        ):
            with self.subTest(text=fragment):
                self.assertNotIn(fragment, html)


class AddressFormTest(TestCase):
    def test_the_demo_banner_says_daily_not_hourly(self):
        with translation.override("de"):
            from django.utils.translation import gettext

            text = gettext("Demo account — data resets daily. Do not enter real personal data.")

        self.assertIn("täglich", text)
        self.assertNotIn("stündlich", text)

    def test_the_tutor_interface_addresses_with_du(self):
        """Stichprobe der Texte, die früher förmlich („Sie“) waren; im übrigen Tutor-Bereich gilt „du“."""
        from django.utils.translation import gettext

        with translation.override("de"):
            for msgid in (
                "Do you really want to delete this invoice?",
                "Please enter a period.",
                "Please correct the errors below.",
                "Network error: Please check your internet connection.",
            ):
                with self.subTest(text=msgid):
                    text = gettext(msgid)
                    self.assertNotRegex(text, r"\b(Sie|Ihre[nmrs]?|Ihr|Ihnen)\b")
                    self.assertNotEqual(text, msgid)


class AuthPagesTest(TestCase):
    def test_tutor_auth_pages_use_the_shared_card_and_label_every_field(self):
        for name in ("core:login", "core:register", "core:password_reset"):
            with self.subTest(seite=name):
                html = self.client.get(reverse(name)).content.decode()
                self.assertIn('class="auth-card"', html)
                self.assertIn("core/css/auth.css", html)
                for input_id in re.findall(
                    r'<input[^>]*type="(?:text|email|password)"[^>]*id="([^"]+)"', html
                ):
                    if input_id == "id_homepage":  # Honeypot, bewusst ohne sichtbare Beschriftung
                        continue
                    self.assertRegex(html, rf'<label[^>]*for="{input_id}"')

    def test_the_login_title_follows_the_language(self):
        for lang, expected in (("de", "Anmelden – Preceptly"), ("en", "Login – Preceptly")):
            with self.subTest(sprache=lang):
                html = get_in(self.client, "core:login", lang).content.decode()
                self.assertIn(f"<title>{expected}</title>", html)

    def test_portal_auth_pages_share_one_base_and_have_a_heading(self):
        for name in ("portal:login", "portal:password_reset"):
            with self.subTest(seite=name):
                html = self.client.get(reverse(name)).content.decode()
                self.assertIn('class="auth-card"', html)
                self.assertIn('<h1 class="auth-title">', html)
                self.assertRegex(html, r'<label[^>]*for="id_email"')
                self.assertIn('lang="de"', html)

    def test_portal_login_still_posts_email_and_password(self):
        html = self.client.get(reverse("portal:login")).content.decode()

        self.assertIn('name="email"', html)
        self.assertIn('name="password"', html)
        self.assertIn('autocomplete="current-password"', html)
