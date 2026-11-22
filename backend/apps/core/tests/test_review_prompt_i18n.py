"""Bewertungsablauf im Dashboard folgt der Sprache.

Befund der Live-Prüfung vom 22.11.2026: Hinweis, Knopf und Dialog hatten deutsche Quelltexte (`msgid`) mit leerer deutscher Übersetzung. In der englischen Oberfläche blieb deshalb alles deutsch.
Jetzt sind die Quelltexte englisch (wie im übrigen Projekt) und die deutsche Oberfläche zeigt wörtlich die bisherigen Texte.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import UserProfile

GERMAN = (
    "Wie zufrieden bist du mit Preceptly? Eine kurze Bewertung hilft anderen Nachhilfelehrern, das Tool zu entdecken.",
    "Bewertung abgeben",
    "Deine Bewertung",
    "Deine Bewertung erscheint erst nach kurzer Prüfung öffentlich auf der Info-Seite.",
    "Was gefällt dir, was fehlt noch?",
    "Absenden",
)
ENGLISH = (
    "How satisfied are you with Preceptly? A short review helps other tutors discover the tool.",
    "Leave a review",
    "Your review",
    "Your review appears publicly on the info page only after a short check.",
    "What do you like, what is still missing?",
    "Submit",
)


class ReviewPromptLanguageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("bewerter", password="pw")
        UserProfile.objects.update_or_create(user=self.user, defaults={"subscription_tier": "pro"})
        self.client.force_login(self.user)

    def dashboard(self, lang):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
        return self.client.get(reverse("core:dashboard")).content.decode()

    def test_the_english_interface_shows_the_prompt_the_button_and_the_dialog_in_english(self):
        html = self.dashboard("en")

        for text in ENGLISH:
            with self.subTest(text=text):
                self.assertIn(text, html)
        for text in GERMAN:
            with self.subTest(deutsch=text):
                self.assertNotIn(
                    text,
                    html,
                    "in der englischen Oberfläche darf der Bewertungsablauf nicht deutsch sein",
                )

    def test_the_german_interface_keeps_the_previous_texts_word_for_word(self):
        html = self.dashboard("de")

        for text in GERMAN:
            with self.subTest(text=text):
                self.assertIn(text, html)
        for text in ENGLISH:
            with self.subTest(englisch=text):
                self.assertNotIn(text, html)
