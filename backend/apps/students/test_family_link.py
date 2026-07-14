"""
Regressionstests für die Familien-Erkennung (Schülerliste) und die
Familien-Verknüpfungs-Aktion (FamilyLinkView).
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.portal.models import ParentStudentLink

User = get_user_model()


class FamilyDetectionAndLinkTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(
            username="family_tutor", password="pass", email="tutor@family.test"
        )
        self.client = Client()
        self.client.login(username="family_tutor", password="pass")

        self.anna = Contract.objects.create(
            user=self.tutor,
            first_name="Anna",
            last_name="Müller",
            email="anna@example.com",
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )
        self.ben = Contract.objects.create(
            user=self.tutor,
            first_name="Ben",
            last_name="Müller",
            email="ben@example.com",
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )
        self.unrelated = Contract.objects.create(
            user=self.tutor,
            first_name="Chris",
            last_name="Schmidt",
            email="chris@example.com",
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )

    def test_same_last_name_is_suggested(self):
        resp = self.client.get(reverse("contracts:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mögliche Familien erkannt")
        self.assertContains(resp, "Anna Müller")
        self.assertContains(resp, "Ben Müller")

    def test_unrelated_contract_not_suggested_together(self):
        resp = self.client.get(reverse("contracts:list"))
        content = resp.content.decode()
        # Chris Schmidt sollte in keinem Vorschlag mit Anna oder Ben auftauchen
        self.assertNotIn("Chris Schmidt</strong> und", content)

    def test_link_family_with_no_existing_account_shows_error(self):
        resp = self.client.post(reverse("students:link_family", args=[self.anna.pk, self.ben.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(ParentStudentLink.objects.count(), 0)

    def test_link_family_reuses_existing_single_account(self):
        self.client.post(
            reverse("students:portal_invite", args=[self.anna.pk]),
            {"email": "family@example.com"},
        )
        self.client.post(reverse("students:link_family", args=[self.anna.pk, self.ben.pk]))
        link_anna = ParentStudentLink.objects.get(contract=self.anna)
        link_ben = ParentStudentLink.objects.get(contract=self.ben)
        self.assertEqual(link_anna.parent_id, link_ben.parent_id)

        # Erkennung sollte das Paar jetzt nicht mehr vorschlagen
        resp = self.client.get(reverse("contracts:list"))
        content = resp.content.decode()
        self.assertNotIn("Anna Müller</strong> und <strong>Ben Müller", content)

    def test_link_family_merges_two_separate_accounts(self):
        self.client.post(
            reverse("students:portal_invite", args=[self.anna.pk]),
            {"email": "anna-account@example.com"},
        )
        self.client.post(
            reverse("students:portal_invite", args=[self.ben.pk]),
            {"email": "ben-account@example.com"},
        )
        link_anna_before = ParentStudentLink.objects.get(contract=self.anna)
        ben_original_account_id = ParentStudentLink.objects.get(contract=self.ben).parent_id

        self.client.post(reverse("students:link_family", args=[self.anna.pk, self.ben.pk]))

        link_anna = ParentStudentLink.objects.get(contract=self.anna)
        self.assertEqual(link_anna.parent_id, link_anna_before.parent_id)

        # Ben hat jetzt zusätzlich einen Link zu Annas Account (Familien-Zugang)
        link_ben_new = ParentStudentLink.objects.get(contract=self.ben, parent=link_anna.parent)
        self.assertIsNotNone(link_ben_new)

        # Der ursprüngliche, jetzt überflüssige Ben-Account ist deaktiviert
        old_ben_link = ParentStudentLink.objects.get(
            contract=self.ben, parent_id=ben_original_account_id
        )
        self.assertFalse(old_ben_link.is_active)
        self.assertFalse(old_ben_link.parent.user.is_active)
