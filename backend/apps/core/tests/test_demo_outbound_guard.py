"""Die öffentlichen Demo-Konten dürfen nichts nach außen auslösen.

Befund vom 20.11.2026: Die Zugangsdaten `demo_user` / `demo123` stehen auf der Start- und der Login-Seite. Mit ihnen konnte jeder Besucher
Portal-Einladungen (und Erneut-Senden, Login-Erinnerungen) an beliebige Adressen von der Preceptly-Domain verschicken lassen, weder gesperrt
noch begrenzt. Außerdem konnte er die Zugangsdaten seines iCloud-Kalenders oder die geheime Adresse seines Google-Kalenders in einem Konto
ablegen, das alle benutzen (die Termine sähen alle, die sich mit den öffentlichen Zugangsdaten anmelden). Beides ist jetzt gesperrt.
"""

from datetime import date
from decimal import Decimal
from unittest import mock

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.calendar_sync.models import CalendarConnection, IcsCalendarSource
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.portal.models import ParentStudentLink, PortalUser
from apps.portal.tests_portal import _make_portal_user, _make_student_link

ICS_URL = (
    "https://calendar.google.com/calendar/ical/abc%40gmail.com/private-0123456789abcdef/basic.ics"
)


def make_tutor(username, tier):
    user = User.objects.create_user(username, password="pw", email=f"{username}@example.com")
    UserProfile.objects.update_or_create(user=user, defaults={"subscription_tier": tier})
    contract = Contract.objects.create(
        user=user,
        first_name="Max",
        last_name="Mustermann",
        email="max@example.com",
        hourly_rate=Decimal("25.00"),
        start_date=date(2026, 1, 1),
        unit_duration_minutes=60,
    )
    return user, contract


def texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class DemoCannotSendEmailsTest(TestCase):
    def setUp(self):
        self.demo, self.contract = make_tutor("demo_premium", "business")
        self.client.force_login(self.demo)

    def test_an_invitation_to_any_address_is_blocked(self):
        response = self.client.post(
            reverse("students:portal_invite", args=[self.contract.pk]),
            {"email": "opfer@example.org"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox, [], "es darf keine E-Mail an eine fremde Adresse gehen")
        self.assertFalse(ParentStudentLink.objects.filter(contract=self.contract).exists())
        self.assertFalse(
            User.objects.filter(email="opfer@example.org").exists(),
            "auch kein Konto für die Adresse",
        )
        self.assertTrue(any("Demo" in text for text in texts(response)), texts(response))

    def test_resending_an_invitation_is_blocked(self):
        portal = _make_portal_user(self.demo, "parent", "eltern_demo", "pw-123456")
        _make_student_link(portal, self.contract, active=False)

        response = self.client.post(
            reverse("students:portal_invite_resend", args=[self.contract.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox, [])

    def test_a_login_reminder_is_blocked(self):
        portal = _make_portal_user(self.demo, "parent", "eltern_demo2", "pw-123456")
        _make_student_link(portal, self.contract, active=True)

        response = self.client.post(
            reverse("students:portal_login_reminder", args=[self.contract.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox, [])

    def test_the_other_demo_account_is_blocked_too(self):
        user, contract = make_tutor("demo_user", "pro")
        self.client.force_login(user)

        self.client.post(
            reverse("students:portal_invite", args=[contract.pk]), {"email": "opfer@example.org"}
        )

        self.assertEqual(mail.outbox, [])
        self.assertFalse(PortalUser.objects.filter(tutor=user).exists())

    def test_an_ordinary_tutor_can_still_invite(self):
        # Gegenprobe: Die Sperre trifft nur die Demo-Konten.
        tutor, contract = make_tutor("echter_tutor", "pro")
        self.client.force_login(tutor)

        self.client.post(
            reverse("students:portal_invite", args=[contract.pk]), {"email": "eltern@example.org"}
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(ParentStudentLink.objects.filter(contract=contract).exists())


@override_settings(CALDAV_ENCRYPTION_KEY=Fernet.generate_key().decode())
class DemoCannotStoreCalendarSecretsTest(TestCase):
    def setUp(self):
        self.demo, _contract = make_tutor("demo_premium", "business")
        self.client.force_login(self.demo)

    def test_a_secret_google_address_is_neither_fetched_nor_stored(self):
        with mock.patch(
            "apps.calendar_sync.views_ics.fetch_ics",
            return_value=b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
        ) as fetch:
            response = self.client.post(
                reverse("calendar_sync:ics_add"), {"name": "Privat", "ics_url": ICS_URL}
            )

        self.assertEqual(response.status_code, 302)
        fetch.assert_not_called()
        self.assertFalse(IcsCalendarSource.objects.filter(user=self.demo).exists())
        self.assertTrue(any("Demo" in text for text in texts(response)), texts(response))

    def test_icloud_credentials_are_neither_tried_nor_stored(self):
        with mock.patch("apps.calendar_sync.views.CalDavClient") as client:
            response = self.client.post(
                reverse("calendar_sync:connect"),
                {
                    "provider": "icloud",
                    "caldav_username": "besucher@icloud.com",
                    "caldav_password": "app-passwort",
                },
            )

        self.assertEqual(response.status_code, 302)
        client.assert_not_called()
        self.assertFalse(CalendarConnection.objects.filter(user=self.demo).exists())

    def test_an_ordinary_tutor_can_still_add_an_address(self):
        # Gegenprobe: Die Sperre trifft nur die Demo-Konten. Der Abgleich selbst ist hier ersetzt: Es geht nur darum, dass der Tutor
        # an der Sperre vorbeikommt, bis die Adresse geholt und gespeichert wird.
        tutor, _contract = make_tutor("echter_tutor", "pro")
        self.client.force_login(tutor)
        ok = {"created": 0, "updated": 0, "deleted": 0}

        with (
            mock.patch(
                "apps.calendar_sync.views_ics.fetch_ics",
                return_value=b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
            ) as fetch,
            mock.patch("apps.calendar_sync.views_ics.sync_source", return_value=ok),
        ):
            self.client.post(
                reverse("calendar_sync:ics_add"), {"name": "Privat", "ics_url": ICS_URL}
            )

        fetch.assert_called_once()
        self.assertTrue(IcsCalendarSource.objects.filter(user=tutor).exists())
