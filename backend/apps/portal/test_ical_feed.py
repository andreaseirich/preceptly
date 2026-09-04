"""
Tests for the read-only portal calendar (iCal) feed.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.lessons.models import Session
from apps.portal.models import ParentStudentLink, PortalUser


class IcalFeedTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="pass")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Max",
            last_name="Muster",
            subjects="Mathe",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        self.portal_django_user = User.objects.create_user(username="parent1", password="pass")
        self.portal_user = PortalUser.objects.create(
            user=self.portal_django_user, role="parent", tutor=self.tutor
        )
        ParentStudentLink.objects.create(
            parent=self.portal_user, contract=self.contract, is_active=True
        )
        self.session = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=1),
            start_time=time(14, 0),
            duration_minutes=60,
        )
        self.client = Client()

    def test_feed_returns_ics_with_session(self):
        url = reverse("portal:ical_feed", args=[self.portal_user.ical_feed_token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/calendar; charset=utf-8")
        body = response.content.decode()
        self.assertIn("BEGIN:VCALENDAR", body)
        self.assertIn(f"preceptly-portal-session-{self.session.pk}@preceptly.de", body)
        self.assertIn("Mathe", body)

    def test_feed_requires_no_login(self):
        # Deliberately not logging in - the token itself is the auth.
        url = reverse("portal:ical_feed", args=[self.portal_user.ical_feed_token])
        response = Client().get(url)
        self.assertEqual(response.status_code, 200)

    def test_invalid_token_returns_404(self):
        response = self.client.get("/portal/calendar-feed/00000000-0000-0000-0000-000000000000.ics")
        self.assertEqual(response.status_code, 404)

    def test_malformed_token_returns_404_not_500(self):
        response = self.client.get("/portal/calendar-feed/not-a-uuid.ics")
        self.assertEqual(response.status_code, 404)

    def test_other_portal_users_sessions_are_not_included(self):
        other_tutor = User.objects.create_user(username="tutor2", password="pass")
        other_contract = Contract.objects.create(
            user=other_tutor,
            first_name="Anna",
            last_name="Beispiel",
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
        )
        other_session = Session.objects.create(
            contract=other_contract,
            date=date.today() + timedelta(days=2),
            start_time=time(10, 0),
            duration_minutes=60,
        )

        url = reverse("portal:ical_feed", args=[self.portal_user.ical_feed_token])
        response = self.client.get(url)
        body = response.content.decode()
        self.assertNotIn(f"preceptly-portal-session-{other_session.pk}@preceptly.de", body)


class ProfileEditIcalLinkTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor3", password="pass")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lisa",
            last_name="Test",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        self.portal_django_user = User.objects.create_user(
            username="parent2", password="StrongPassw0rd!"
        )
        self.portal_user = PortalUser.objects.create(
            user=self.portal_django_user, role="parent", tutor=self.tutor
        )
        ParentStudentLink.objects.create(
            parent=self.portal_user, contract=self.contract, is_active=True
        )
        self.client = Client()
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

    def test_profile_page_shows_feed_url_with_correct_token(self):
        response = self.client.get(reverse("portal:profile"))
        self.assertContains(response, str(self.portal_user.ical_feed_token))
        self.assertContains(response, "/portal/calendar-feed/")
