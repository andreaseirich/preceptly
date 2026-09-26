"""Schüler und Eltern müssen den Portal-Login ohne Umweg finden."""

from django.test import TestCase
from django.urls import reverse


class PortalEntryLinkTest(TestCase):
    def test_login_page_links_to_portal_login(self):
        response = self.client.get(reverse("core:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("portal:login")}"')
        self.assertContains(response, "Portal-Login")

    def test_landing_page_explains_how_students_get_access(self):
        response = self.client.get(reverse("core:landing"), HTTP_ACCEPT_LANGUAGE="de")

        self.assertContains(response, "Schüler oder Eltern?")
        self.assertContains(response, "E-Mail-Einladung von deinem Nachhilfelehrer")

    def test_landing_page_links_to_portal_login(self):
        response = self.client.get(reverse("core:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("portal:login")}"')
        self.assertContains(response, "Portal-Login")
