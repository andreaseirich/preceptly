"""
Regressionstests für den vereinheitlichten Portal-Einladungs-Flow
(PortalInviteView): ein gemeinsamer Account pro Kind, Familien-Zugang
bei einer zweiten Einladung mit derselben E-Mail-Adresse.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.portal.models import ParentStudentLink

User = get_user_model()


class PortalInviteViewTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(
            username="invite_tutor", password="pass", email="tutor@invite.test"
        )
        self.client = Client()
        self.client.login(username="invite_tutor", password="pass")

        self.contract_a = Contract.objects.create(
            user=self.tutor,
            first_name="Anna",
            last_name="Müller",
            email="anna@example.com",
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )
        self.contract_b = Contract.objects.create(
            user=self.tutor,
            first_name="Ben",
            last_name="Müller",
            email="ben@example.com",
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )

    def test_invite_creates_single_shared_link(self):
        """Eine Einladung legt genau einen Account + einen aktiven Link an."""
        resp = self.client.post(
            reverse("students:portal_invite", args=[self.contract_a.pk]),
            {"email": "parent@example.com"},
        )
        self.assertEqual(resp.status_code, 302)
        links = ParentStudentLink.objects.filter(contract=self.contract_a)
        self.assertEqual(links.count(), 1)
        self.assertEqual(links.first().parent.user.email, "parent@example.com")

    def test_second_invite_same_email_links_existing_account(self):
        """Zweite Einladung mit gleicher E-Mail für ein anderes Kind verknüpft
        denselben Account (Familien-Zugang), statt einen neuen anzulegen."""
        self.client.post(
            reverse("students:portal_invite", args=[self.contract_a.pk]),
            {"email": "family@example.com"},
        )
        self.client.post(
            reverse("students:portal_invite", args=[self.contract_b.pk]),
            {"email": "family@example.com"},
        )
        link_a = ParentStudentLink.objects.get(contract=self.contract_a)
        link_b = ParentStudentLink.objects.get(contract=self.contract_b)
        self.assertEqual(link_a.parent_id, link_b.parent_id)
        self.assertEqual(User.objects.filter(email="family@example.com").count(), 1)

    def test_invite_twice_same_contract_is_noop(self):
        """Eine zweite Einladung für denselben Vertrag legt keinen zweiten Link an."""
        self.client.post(
            reverse("students:portal_invite", args=[self.contract_a.pk]),
            {"email": "first@example.com"},
        )
        self.client.post(
            reverse("students:portal_invite", args=[self.contract_a.pk]),
            {"email": "second@example.com"},
        )
        self.assertEqual(ParentStudentLink.objects.filter(contract=self.contract_a).count(), 1)

    def test_invite_cross_tenant_rejected(self):
        """Eine E-Mail, die bereits einem Portal-Account eines ANDEREN Tutors
        gehört, darf nicht verknüpft werden."""
        other_tutor = User.objects.create_user(
            username="other_tutor", password="pass", email="other@invite.test"
        )
        other_contract = Contract.objects.create(
            user=other_tutor,
            first_name="Other",
            last_name="Kid",
            email="otherkid@example.com",
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )
        self.client.login(username="other_tutor", password="pass")
        self.client.post(
            reverse("students:portal_invite", args=[other_contract.pk]),
            {"email": "shared@example.com"},
        )
        self.client.login(username="invite_tutor", password="pass")
        self.client.post(
            reverse("students:portal_invite", args=[self.contract_a.pk]),
            {"email": "shared@example.com"},
        )
        self.assertFalse(ParentStudentLink.objects.filter(contract=self.contract_a).exists())

    def test_contract_detail_shows_invite_form_and_link_status(self):
        """Vertragsdetailseite zeigt Einladungsformular bzw. Account-Status."""
        resp = self.client.get(reverse("contracts:detail", args=[self.contract_a.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Portal-Einladung senden")

        self.client.post(
            reverse("students:portal_invite", args=[self.contract_a.pk]),
            {"email": "parent2@example.com"},
        )
        resp = self.client.get(reverse("contracts:detail", args=[self.contract_a.pk]))
        self.assertContains(resp, "parent2@example.com")
        self.assertContains(resp, "Einladung ausstehend")
