"""
The calendar feed URL is protected only by the token it contains, and such
URLs end up in Google/Apple calendars and get forwarded. Portal users can
now issue a new token themselves.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.portal.models import ParentStudentLink, PortalUser


class IcalFeedRenewTest(TestCase):
    def setUp(self):
        tutor = User.objects.create_user(username="tutor_feed", password="pass")
        contract = Contract.objects.create(
            user=tutor,
            first_name="Max",
            last_name="Muster",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        parent = User.objects.create_user(username="parent_feed", password="pass")
        self.portal_user = PortalUser.objects.create(user=parent, role="parent", tutor=tutor)
        ParentStudentLink.objects.create(parent=self.portal_user, contract=contract, is_active=True)
        self.client = Client()
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

    def test_renewing_replaces_the_token_and_kills_the_old_url(self):
        old_token = self.portal_user.ical_feed_token
        old_url = reverse("portal:ical_feed", args=[old_token])
        self.assertEqual(self.client.get(old_url).status_code, 200)

        response = self.client.post(reverse("portal:ical_feed_renew"))
        self.assertRedirects(response, reverse("portal:profile"))

        self.portal_user.refresh_from_db()
        self.assertNotEqual(self.portal_user.ical_feed_token, old_token)
        self.assertEqual(self.client.get(old_url).status_code, 404)
        new_url = reverse("portal:ical_feed", args=[self.portal_user.ical_feed_token])
        self.assertEqual(self.client.get(new_url).status_code, 200)

    def test_requires_a_portal_session(self):
        anonymous = Client()
        response = anonymous.post(reverse("portal:ical_feed_renew"))
        self.assertRedirects(response, reverse("portal:login"), fetch_redirect_response=False)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("portal:ical_feed_renew")).status_code, 405)
