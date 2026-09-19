from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Session
from apps.portal.models import ParentStudentLink, PortalUser

HINT = "etwa eine halbe Stunde Puffer"


class PortalBufferHintTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor_bh", password="pass")
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Max",
            last_name="Muster",
            hourly_rate=Decimal("20.00"),
            start_date=date.today(),
        )
        parent = User.objects.create_user(username="parent_bh", password="pass")
        portal_user = PortalUser.objects.create(user=parent, role="parent", tutor=self.tutor)
        ParentStudentLink.objects.create(parent=portal_user, contract=self.contract, is_active=True)
        self.lesson = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=3),
            start_time=time(15, 0),
            duration_minutes=60,
        )
        self.client = Client()
        session = self.client.session
        session["portal_user_id"] = portal_user.pk
        session.save()

    def _booking_urls(self):
        return [
            reverse("portal:book", args=[self.contract.pk]),
            reverse("portal:session_reschedule", args=[self.lesson.pk]),
            reverse("portal:recurring_create", args=[self.contract.pk]),
        ]

    def test_hint_shown_by_default_wherever_a_time_is_picked(self):
        for url in self._booking_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, HINT)

    def test_booking_page_shows_hint_at_calendar_and_at_slot_list(self):
        response = self.client.get(reverse("portal:book", args=[self.contract.pk]))
        self.assertContains(response, HINT, count=2)

    def test_hint_hidden_when_tutor_turns_it_off(self):
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"portal_buffer_hint_enabled": False}
        )
        for url in self._booking_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, HINT)
