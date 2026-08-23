"""
Tests for the "under active development" beta notice modal shown once per
browser session on both the tutor app and the portal.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class TutorBetaNoticeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = User.objects.create_user(username="tutor", password="test")
        self.client.force_login(self.tutor)

    def test_dashboard_contains_beta_notice_modal(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="betaNoticeOverlay"', content)
        self.assertIn("beta_notice_dismissed_forever", content)
        self.assertIn("mailto:andreas@preceptly.de", content)


class PortalBetaNoticeTest(TestCase):
    """The login page itself is a standalone template (no base.html), so
    this checks an authenticated portal page, which does extend base.html."""

    def setUp(self):
        from apps.portal.models import PortalUser

        self.client = Client()
        self.tutor = User.objects.create_user(username="tutor2", password="test")
        portal_django_user = User.objects.create_user(username="student1", password="test")
        self.portal_user = PortalUser.objects.create(
            user=portal_django_user, role="student", tutor=self.tutor
        )
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

    def test_portal_page_contains_beta_notice_modal(self):
        response = self.client.get(reverse("portal:profile"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="betaNoticeOverlay"', content)
        self.assertIn("beta_notice_dismissed_forever_portal", content)
