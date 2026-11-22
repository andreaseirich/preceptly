"""Feste Texte der Tutor-App folgen der Sprache.

Befund der Live-Prüfung vom 22.11.2026: `aria-label`, `title` und `placeholder` standen fest auf Deutsch in den Vorlagen, ein Quelltext („Fortschrittsnotiz hinzufügen“) war deutsch. Screenreader lasen sie in der
englischen Oberfläche deutsch vor. Der Wächter sucht solche Stellen in den Vorlagen der Tutor-App (Portal, E-Mails, Rechtstexte, PDF, Meetingraum und FAQ sind bewusst deutsch beziehungsweise ausgenommen).
"""

import glob
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import UserProfile

ROOT = Path(__file__).resolve().parents[3]
SKIP = ("/portal/", "/email/", "invoice_document", "meeting/room", "/legal/", "faq.html")
UML = "äöüßÄÖÜ"
FIXED_ATTRIBUTE = re.compile(r'(?:aria-label|title|placeholder|alt)="([^"{]*)"')
GERMAN_WORD = re.compile(
    r"\b(Heutige|Nächste|Schüler\w*|Stunden\w*|Zurück|Speichern|Löschen|Abbrechen|Beträge|Lektion\w*)\b"
)


def templates():
    found = glob.glob(str(ROOT / "apps/**/templates/**/*.html"), recursive=True) + glob.glob(
        str(ROOT / "templates/**/*.html"), recursive=True
    )
    return [Path(f) for f in found if not any(k in f for k in SKIP)]


def looks_german(text):
    return bool(re.search(f"[{UML}]", text.replace("EÜR", "").replace("Müller", ""))) or bool(
        GERMAN_WORD.search(text)
    )


class NoFixedGermanTextsTest(TestCase):
    def test_no_attribute_with_a_fixed_german_text(self):
        found = []
        for path in templates():
            for match in FIXED_ATTRIBUTE.finditer(path.read_text(encoding="utf-8")):
                if looks_german(match.group(1)):
                    found.append(f"{path.relative_to(ROOT)}: {match.group(0)[:80]}")

        self.assertEqual(
            found, [], "Feste deutsche Attribute: mit {% trans 'English' %} übersetzbar machen"
        )

    def test_no_translation_source_text_is_german(self):
        found = []
        for path in templates():
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"""\{%\s*trans\s+["']([^"']*)["']""", text):
                if looks_german(match.group(1)):
                    found.append(f"{path.relative_to(ROOT)}: {match.group(1)[:60]}")

        self.assertEqual(
            found, [], "Quelltexte sind englisch, die deutsche Fassung steht in locale/de"
        )


class FixedTextsFollowTheLanguageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("festtexte", password="pw")
        UserProfile.objects.update_or_create(user=self.user, defaults={"subscription_tier": "pro"})
        self.client.force_login(self.user)

    def page(self, name, lang):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
        return self.client.get(reverse(name)).content.decode()

    def test_the_student_list_label_follows_the_language(self):
        Contract.objects.create(
            user=self.user,
            first_name="Eva",
            last_name="Beispiel",
            hourly_rate=Decimal("20"),
            start_date=date.today(),
        )

        self.assertIn('aria-label="Student list"', self.page("students:list", "en"))
        self.assertIn('aria-label="Schülerliste"', self.page("students:list", "de"))
