"""
Tests for contract deactivation behavior.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contracts.models import Contract
from apps.lessons.models import Lesson


class ContractDeactivateDeletesFutureLessonsTest(TestCase):
    """When contract is set to inactive, future lessons are deleted."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tutor", email="tutor@test.com", password="test123"
        )
        self.student = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Test",
            last_name="Student",
            email="test@example.com",
        )
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Student",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
            is_active=True,
        )

    def test_deactivate_deletes_future_lessons(self):
        """Setting is_active=False deletes all future lessons."""
        today = date.today()
        past_date = today - timedelta(days=5)
        future_date = today + timedelta(days=7)

        Lesson.objects.create(
            contract=self.contract,
            date=past_date,
            start_time="10:00",
            duration_minutes=60,
            status="taught",
        )
        Lesson.objects.create(
            contract=self.contract,
            date=future_date,
            start_time="10:00",
            duration_minutes=60,
            status="planned",
        )

        self.assertEqual(Lesson.objects.filter(contract=self.contract).count(), 2)

        self.contract.is_active = False
        self.contract.save()

        remaining = Lesson.objects.filter(contract=self.contract)
        self.assertEqual(remaining.count(), 1)
        self.assertEqual(remaining.first().date, past_date)


class ContractDeactivateKeepsEverythingButPlannedLessonsTest(TestCase):
    """Beim Inaktivsetzen fallen nur geplante Stunden ab heute weg.

    Gehaltene, bezahlte und abgesagte Stunden bleiben, auch wenn sie von heute oder aus der Zukunft sind: An ihnen hängen
    Rechnungen, Einnahmen und Steuern. Vorher wurde jede Stunde ab heute gelöscht, gleich welchen Status sie hatte.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test123")
        self.contract = self.make_contract("Max")
        self.today = timezone.localdate()

    def make_contract(self, first):
        return Contract.objects.create(
            user=self.user,
            first_name=first,
            last_name="Muster",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date.today() - timedelta(days=30),
            is_active=True,
        )

    def lesson(self, days, status, contract=None):
        return Lesson.objects.create(
            contract=contract or self.contract,
            date=self.today + timedelta(days=days),
            start_time="10:00",
            duration_minutes=60,
            status=status,
        )

    def deactivate(self):
        self.contract.is_active = False
        self.contract.save()

    def test_only_planned_lessons_from_today_on_are_deleted(self):
        planned_today = self.lesson(0, "planned")
        planned_later = self.lesson(7, "planned")
        taught_today = self.lesson(0, "taught")
        paid_today = self.lesson(0, "paid")
        taught_later = self.lesson(3, "taught")
        cancelled_later = self.lesson(5, "cancelled")

        self.deactivate()

        remaining = set(Lesson.objects.filter(contract=self.contract).values_list("pk", flat=True))
        self.assertEqual(
            remaining, {taught_today.pk, paid_today.pk, taught_later.pk, cancelled_later.pk}
        )
        self.assertFalse(
            Lesson.objects.filter(pk__in=[planned_today.pk, planned_later.pk]).exists()
        )

    def test_a_paid_lesson_of_today_survives(self):
        # Genau der Fall, der vorher still verloren ging: bezahlt, aber das Datum ist heute.
        paid = self.lesson(0, "paid")

        self.deactivate()

        self.assertTrue(Lesson.objects.filter(pk=paid.pk).exists())

    def test_planned_lessons_in_the_past_are_left_alone(self):
        # Noch "geplant", aber vorbei (die Automatik hat sie noch nicht auf "gehalten" gesetzt): Vergangenheit bleibt.
        yesterday = self.lesson(-1, "planned")

        self.deactivate()

        self.assertTrue(Lesson.objects.filter(pk=yesterday.pk).exists())

    def test_other_students_lessons_are_untouched(self):
        other = self.make_contract("Anna")
        theirs = self.lesson(2, "planned", contract=other)
        self.lesson(2, "planned")

        self.deactivate()

        self.assertTrue(Lesson.objects.filter(pk=theirs.pk).exists())

    def test_the_toggle_button_behaves_the_same(self):
        planned = self.lesson(2, "planned")
        taught = self.lesson(2, "taught")
        self.client.login(username="tutor", password="test123")

        response = self.client.post(reverse("contracts:toggle_active", args=[self.contract.pk]))

        self.assertEqual(response.status_code, 302)
        self.contract.refresh_from_db()
        self.assertFalse(self.contract.is_active)
        self.assertFalse(Lesson.objects.filter(pk=planned.pk).exists())
        self.assertTrue(Lesson.objects.filter(pk=taught.pk).exists())

    def test_activating_again_deletes_nothing(self):
        self.deactivate()
        planned = self.lesson(4, "planned")

        self.contract.is_active = True
        self.contract.save()

        self.assertTrue(Lesson.objects.filter(pk=planned.pk).exists())

    def test_saving_an_active_contract_deletes_nothing(self):
        planned = self.lesson(4, "planned")

        self.contract.notes = "Neue Notiz"
        self.contract.save()

        self.assertTrue(Lesson.objects.filter(pk=planned.pk).exists())

    def test_deactivating_twice_is_harmless(self):
        self.deactivate()
        planned = self.lesson(4, "planned")  # nach dem Inaktivsetzen von Hand angelegt

        self.contract.save()  # weiterhin inaktiv: war schon inaktiv, also kein Löschen

        self.assertTrue(Lesson.objects.filter(pk=planned.pk).exists())
