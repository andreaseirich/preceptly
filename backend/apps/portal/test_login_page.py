"""Portal-Anmeldeseite: Rückweg zum Tutor-Login und Layout auf dem Handy."""

from django.test import TestCase
from django.urls import reverse


class PortalLoginPageTest(TestCase):
    def test_links_back_to_the_tutor_login(self):
        response = self.client.get(reverse("portal:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("core:login")}"')
        self.assertContains(response, "Zum Tutor-Login")

    def test_card_and_legal_footer_stack_instead_of_sitting_side_by_side(self):
        """Ohne flex-direction: column schneidet die Fußzeile auf dem Handy die
        Anmeldekarte ab - sie werden sonst zu zwei Spalten nebeneinander."""
        for name in ("portal:login", "portal:password_reset"):
            with self.subTest(seite=name):
                body = self.client.get(reverse(name)).content.decode()
                self.assertIn("flex-direction: column", body)
