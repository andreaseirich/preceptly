"""Zweites Kind am selben Eltern-Konto: sofort sichtbar, kein zweites Passwort.

Befund vom 24.11.2026 (Familie Charlier): Der Vater hatte für Leon sein Konto aktiviert. Für Laura mit derselben E-Mail-Adresse legte das System nur eine Verknüpfung an, die inaktiv blieb: keine Mail, Laura im Portal unsichtbar, und der Tutor sah nur die Meldung „verknüpft“. Eine erneute Einladung hätte das Passwort des Kontos überschrieben.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.portal.models import ParentStudentLink

User = get_user_model()
FAMILY_MAIL = "familie@example.org"
PASSWORD = "Sehr-sicher-4711"


class SecondChildTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(
            username="tutor_zweitkind", password="pw", email="t@example.org"
        )
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        self.client = Client()
        self.client.login(username="tutor_zweitkind", password="pw")
        self.leon = self.child("Leon")
        self.laura = self.child("Laura")

    def child(self, first_name):
        return Contract.objects.create(
            user=self.tutor,
            first_name=first_name,
            last_name="Charlier",
            parent_email=FAMILY_MAIL,
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )

    def invite(self, contract):
        return self.client.post(
            reverse("students:portal_invite", args=[contract.pk]), {"email": FAMILY_MAIL}
        )

    def activate(self, contract, password=PASSWORD):
        link = ParentStudentLink.objects.get(contract=contract)
        return Client().post(
            reverse("portal:activate", args=[link.invite_token]),
            {"password": password, "password_confirm": password},
        )

    def test_the_second_child_of_an_active_account_is_visible_at_once(self):
        self.invite(self.leon)
        self.activate(self.leon)
        mail.outbox.clear()

        self.invite(self.laura)

        link = ParentStudentLink.objects.get(contract=self.laura)
        self.assertTrue(link.is_active)
        self.assertEqual(
            link.parent_id, ParentStudentLink.objects.get(contract=self.leon).parent_id
        )

    def test_the_parent_gets_a_mail_about_the_new_child_without_an_activation_link(self):
        self.invite(self.leon)
        self.activate(self.leon)
        mail.outbox.clear()

        self.invite(self.laura)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [FAMILY_MAIL])
        self.assertIn("Laura", message.body)
        self.assertIn("/portal/login/", message.body)
        self.assertNotIn("/portal/activate/", message.body)
        self.assertIn("kein neues Passwort", message.body)
        self.assertIn("Laura", message.alternatives[0][0])

    def test_the_family_password_stays_as_the_parent_chose_it(self):
        self.invite(self.leon)
        self.activate(self.leon)
        self.invite(self.laura)

        reply = Client().post(
            "/portal/login/", {"email": FAMILY_MAIL, "password": PASSWORD}, follow=False
        )

        self.assertEqual(reply.status_code, 302)
        self.assertNotIn("/portal/login/", reply["Location"])

    def test_a_pending_first_invite_keeps_the_second_child_inactive_until_activation(self):
        self.invite(self.leon)
        mail.outbox.clear()

        self.invite(self.laura)

        self.assertFalse(ParentStudentLink.objects.get(contract=self.laura).is_active)
        self.assertEqual(mail.outbox, [], "die Einladung für das erste Kind kommt schon")

        self.activate(self.leon)

        self.assertTrue(ParentStudentLink.objects.get(contract=self.laura).is_active)

    def test_linking_a_family_by_hand_also_shows_the_child_and_tells_the_parent(self):
        self.invite(self.leon)
        self.activate(self.leon)
        mail.outbox.clear()

        self.client.post(reverse("students:link_family", args=[self.leon.pk, self.laura.pk]))

        self.assertTrue(ParentStudentLink.objects.get(contract=self.laura).is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Laura", mail.outbox[0].body)

    def test_activation_never_touches_the_links_of_other_accounts(self):
        other = self.child("Mia")
        other.parent_email = "andere@example.org"
        other.save()
        self.invite(self.leon)
        self.client.post(
            reverse("students:portal_invite", args=[other.pk]), {"email": "andere@example.org"}
        )

        self.activate(self.leon)

        self.assertFalse(ParentStudentLink.objects.get(contract=other).is_active)
