"""Registrierung: Honeypot gegen Automaten.

Auftrag von Andreas, 26.10.2026. Anlass: Am 25.10.2026 meldete die App eine Registrierung mit Zufallsnamen und der
Adresse eines Formular-Test-Dienstes, vermutlich ein Automat. Das Feld "homepage" ist für Menschen unsichtbar; Automaten
füllen es aus, dann wird nichts angelegt.
"""

import re

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.forms import HONEYPOT_FIELD, RegisterForm

GERMAN_ERROR = "Registrierung fehlgeschlagen. Bitte versuche es erneut."


class HoneypotFixture(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("core:register")

    def data(self, **extra):
        data = {
            "username": "botuser",
            "email": "bot@example.com",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
            "avv_consent": "on",
        }
        data.update(extra)
        return data

    def register(self, **extra):
        return self.client.post(self.url, self.data(**extra))


class FormTest(HoneypotFixture):
    def test_the_field_name_is_the_one_the_page_uses(self):
        self.assertEqual(HONEYPOT_FIELD, "homepage")

    def test_without_the_field_the_form_is_valid(self):
        self.assertTrue(RegisterForm(data=self.data()).is_valid())

    def test_an_empty_field_is_valid(self):
        self.assertTrue(RegisterForm(data=self.data(homepage="")).is_valid())

    def test_a_filled_field_is_rejected_with_the_generic_message(self):
        form = RegisterForm(data=self.data(homepage="http://spam.example"))

        self.assertFalse(form.is_valid())
        error = form.non_field_errors().as_data()[0]
        self.assertEqual(error.code, "honeypot")

    def test_even_a_single_space_counts_as_filled(self):
        self.assertFalse(RegisterForm(data=self.data(homepage=" ")).is_valid())

    def test_the_field_is_optional_so_other_forms_with_it_are_not_affected(self):
        self.assertFalse(RegisterForm().fields["homepage"].required)


class RegistrationFlowTest(HoneypotFixture):
    def test_a_normal_registration_still_works(self):
        response = self.register()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="botuser").exists())
        self.assertGreaterEqual(len(mail.outbox), 1)  # Bestätigung und Meldung an dich

    def test_a_normal_registration_with_the_empty_field_works_too(self):
        response = self.register(homepage="")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="botuser").exists())

    def test_a_filled_honeypot_creates_no_account_and_sends_no_mail(self):
        response = self.register(homepage="http://spam.example")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="botuser").exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, GERMAN_ERROR)

    def test_the_page_does_not_echo_what_the_bot_typed(self):
        response = self.register(homepage="http://spam.example")

        self.assertNotContains(response, "spam.example")
        field = re.search(r'<input[^>]*name="homepage"[^>]*>', response.content.decode())
        self.assertIn('value=""', field.group(0))

    def test_a_human_can_simply_try_again_after_a_false_alarm(self):
        self.register(homepage="x")

        response = self.register()  # zweiter Versuch, Feld leer

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="botuser").exists())

    def test_the_log_names_neither_user_nor_address(self):
        with self.assertLogs("apps.core.forms", level="WARNING") as logs:
            self.register(homepage="x", username="geheimername", email="geheim@example.com")

        output = "\n".join(logs.output)
        self.assertIn("honeypot", output)
        self.assertNotIn("geheimername", output)
        self.assertNotIn("geheim@example.com", output)

    def test_rejected_attempts_still_count_towards_the_throttle(self):
        for _ in range(5):
            self.register(homepage="x")

        response = self.register(homepage="x")

        self.assertEqual(response.status_code, 429)


class PageTest(HoneypotFixture):
    def field_tag(self):
        html = self.client.get(self.url).content.decode()
        return html, re.search(r'<input[^>]*name="homepage"[^>]*>', html).group(0)

    def test_the_field_is_on_the_page_but_out_of_reach(self):
        html, tag = self.field_tag()

        self.assertIn('tabindex="-1"', tag)
        self.assertIn('autocomplete="off"', tag)
        self.assertNotIn("required", tag)
        self.assertIn('value=""', tag)
        # Umschlag: für Screenreader versteckt, optisch aus dem Bild genommen
        wrapper = html[
            html.rfind("<div", 0, html.find('name="homepage"')) : html.find('name="homepage"')
        ]
        self.assertIn('aria-hidden="true"', wrapper)
        self.assertIn("clip: rect(0, 0, 0, 0)", wrapper)

    def test_it_is_not_hidden_with_display_none(self):
        html, _tag = self.field_tag()

        start = html.rfind("<div", 0, html.find('name="homepage"'))
        self.assertNotIn("display: none", html[start : html.find("</div>", start)])
        self.assertNotIn("display:none", html[start : html.find("</div>", start)])

    def test_there_is_a_label_for_those_without_css(self):
        html, _tag = self.field_tag()

        self.assertIn('<label for="id_homepage">Bitte lass dieses Feld leer.</label>', html)

    def test_the_real_fields_stay_focusable_and_the_first_one_has_the_focus(self):
        html, _tag = self.field_tag()

        self.assertIn('id="id_username" required autofocus', html)
        self.assertEqual(html.count('name="homepage"'), 1)
