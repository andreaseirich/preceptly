"""E-Mail-Eindeutigkeit für Portal-Zugänge.

Ein Login wird über die E-Mail des Django-Users gefunden oder — als Rückfall
für Alt-Zugänge — über die Vertrags-E-Mail eines ``StudentPortalLink``.
Wer eine fremde Login-E-Mail übernimmt, sperrt den anderen aus.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.portal.identity import portal_login_conflict
from apps.portal.models import ParentStudentLink, PortalUser, StudentPortalLink


def _contract(tutor, first_name, last_name, email=None):
    return Contract.objects.create(
        user=tutor,
        first_name=first_name,
        last_name=last_name,
        email=email,
        subjects="Mathe",
        hourly_rate=Decimal("20.00"),
        start_date=date.today(),
    )


class PortalLoginConflictTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="pass")

    def test_no_conflict_for_free_email(self):
        self.assertFalse(portal_login_conflict("frei@example.com"))

    def test_empty_email_is_no_conflict(self):
        self.assertFalse(portal_login_conflict(""))
        self.assertFalse(portal_login_conflict(None))

    def test_existing_portal_user_email_conflicts(self):
        django_user = User.objects.create_user(
            username="p1", password="pass", email="Eltern@Example.com"
        )
        PortalUser.objects.create(user=django_user, role="parent", tutor=self.tutor)

        self.assertTrue(portal_login_conflict("eltern@example.com"))
        self.assertFalse(
            portal_login_conflict("eltern@example.com", exclude_user_pk=django_user.pk)
        )

    def test_user_without_portal_profile_does_not_conflict(self):
        User.objects.create_user(username="tutor2", password="pass", email="tutor2@example.com")
        self.assertFalse(portal_login_conflict("tutor2@example.com"))

    def test_legacy_student_link_contract_email_conflicts(self):
        contract = _contract(self.tutor, "Lea", "Schmidt", email="lea@example.com")
        django_user = User.objects.create_user(username="s1", password="pass")
        portal_user = PortalUser.objects.create(user=django_user, role="student", tutor=self.tutor)
        StudentPortalLink.objects.create(portal_user=portal_user, contract=contract)

        self.assertTrue(portal_login_conflict("lea@example.com"))
        self.assertFalse(portal_login_conflict("lea@example.com", exclude_contract_pk=contract.pk))


class PortalProfileEmailChangeTest(TestCase):
    """Der Eltern-Zugang darf keine fremde Login-E-Mail übernehmen."""

    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="pass")

        # Alt-Zugang: Login läuft über die Vertrags-E-Mail, nicht über den User.
        self.legacy_contract = _contract(self.tutor, "Lea", "Schmidt", email="lea@example.com")
        legacy_user = User.objects.create_user(username="legacy", password="pass")
        legacy_portal = PortalUser.objects.create(
            user=legacy_user, role="student", tutor=self.tutor
        )
        StudentPortalLink.objects.create(
            portal_user=legacy_portal, contract=self.legacy_contract, is_active=True
        )

        # Angreifender Zugang mit eigenem Vertrag.
        self.contract = _contract(self.tutor, "Max", "Muster", email="max@example.com")
        self.django_user = User.objects.create_user(
            username="parent", password="pass", email="max@example.com"
        )
        self.portal_user = PortalUser.objects.create(
            user=self.django_user, role="parent", tutor=self.tutor
        )
        ParentStudentLink.objects.create(
            parent=self.portal_user, contract=self.contract, is_active=True
        )

        self.client = Client()
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

    def test_cannot_take_over_legacy_login_email(self):
        response = self.client.post(
            reverse("portal:profile"),
            {"action": "contact", "email": "lea@example.com", "phone": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bereits von einem anderen Konto")
        self.django_user.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(self.django_user.email, "max@example.com")
        self.assertEqual(self.contract.email, "max@example.com")

    def test_free_email_is_accepted(self):
        response = self.client.post(
            reverse("portal:profile"),
            {"action": "contact", "email": "neu@example.com", "phone": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.django_user.refresh_from_db()
        self.contract.refresh_from_db()
        self.assertEqual(self.django_user.email, "neu@example.com")
        self.assertEqual(self.contract.email, "neu@example.com")


class PortalInviteEmailConflictTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="tutor", password="pass")
        self.client = Client()
        self.client.force_login(self.tutor)

        self.legacy_contract = _contract(self.tutor, "Lea", "Schmidt", email="lea@example.com")
        legacy_user = User.objects.create_user(username="legacy", password="pass")
        self.legacy_portal = PortalUser.objects.create(
            user=legacy_user, role="student", tutor=self.tutor
        )
        StudentPortalLink.objects.create(
            portal_user=self.legacy_portal, contract=self.legacy_contract, is_active=True
        )

    def test_invite_with_legacy_login_email_is_blocked(self):
        contract = _contract(self.tutor, "Max", "Muster", email="max@example.com")

        response = self.client.post(
            reverse("students:portal_invite", args=[contract.pk]),
            {"email": "lea@example.com"},
            follow=True,
        )

        self.assertContains(response, "bereits zu einem anderen Portal-Zugang")
        self.assertFalse(ParentStudentLink.objects.filter(contract=contract).exists())
        self.assertFalse(User.objects.filter(email__iexact="lea@example.com").exists())

    def test_contract_with_legacy_link_is_not_invited_twice(self):
        response = self.client.post(
            reverse("students:portal_invite", args=[self.legacy_contract.pk]),
            {"email": "lea@example.com"},
            follow=True,
        )

        self.assertContains(response, "bereits vorhanden")
        self.assertFalse(ParentStudentLink.objects.filter(contract=self.legacy_contract).exists())
