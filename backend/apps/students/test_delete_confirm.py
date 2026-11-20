"""Schüler löschen: Die Bestätigungsseite zeigt den Namen, führt zurück zum Vertrag und löscht erst nach dem Absenden.

Befund vom 20.11.2026: GET /students/<id>/delete/ endete mit HTTP 500 (NoReverseMatch). Die View ist eine DeleteView auf Contract und liefert
`object`/`contract`, die Vorlage las aber `student` und baute daraus den Link „Abbrechen“. Der Name im Fragesatz blieb dadurch auch leer.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import UserProfile


class StudentDeleteConfirmTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("tutor_loeschen", password="pw")
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Erika",
            last_name="Musterfrau",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2026, 1, 1),
        )
        self.client.force_login(self.tutor)
        self.url = reverse("students:delete", args=[self.contract.pk])

    def test_the_confirmation_page_renders(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_it_names_the_student_and_links_back_to_the_contract(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Erika Musterfrau")
        self.assertContains(
            response, f'href="{reverse("contracts:detail", args=[self.contract.pk])}"'
        )

    def test_the_delete_button_carries_the_name_for_screen_readers(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'aria-label="Schüler Erika Musterfrau löschen"')

    def test_nothing_is_deleted_by_just_opening_the_page(self):
        self.client.get(self.url)

        self.assertTrue(Contract.objects.filter(pk=self.contract.pk).exists())

    def test_posting_deletes_the_student(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Contract.objects.filter(pk=self.contract.pk).exists())

    def test_a_foreign_tutor_gets_404(self):
        other = User.objects.create_user("anderer_tutor", password="pw")
        self.client.force_login(other)

        self.assertEqual(self.client.get(self.url).status_code, 404)
