"""Tarif-Sperren für Serien, Sperrzeiten, Schüler-Portal, Familien-Zugang und Meetings.

Regel: gesperrt heißt, nichts Neues anlegen und nichts ändern. Ansehen,
absagen und löschen bleibt möglich, bestehende Portal-Konten bleiben aktiv.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession
from apps.meeting.models import MeetingRoom
from apps.portal.models import ParentStudentLink, PortalUser


class GateFixture(TestCase):
    tier = "free"

    def setUp(self):
        self.tutor = User.objects.create_user(username=f"tutor_{self.tier}", password="pass")
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"subscription_tier": self.tier}
        )
        self.contract = self._contract("Lea", "lea@example.com")
        self.client.force_login(self.tutor)

    def _contract(self, first_name, email):
        return Contract.objects.create(
            user=self.tutor,
            first_name=first_name,
            last_name="Schmidt",
            email=email,
            hourly_rate=Decimal("25.00"),
            start_date=date.today() - timedelta(days=30),
        )

    def _series(self):
        return RecurringSession.objects.create(
            contract=self.contract,
            start_date=date.today() + timedelta(days=7),
            start_time=time(15, 0),
            duration_minutes=60,
            recurrence_type="weekly",
            monday=True,
            is_active=True,
        )

    def _blocked_time(self):
        start = timezone.make_aware(datetime.combine(date.today() + timedelta(days=3), time(10, 0)))
        return BlockedTime.objects.create(
            user=self.tutor,
            title="Arzt",
            start_datetime=start,
            end_datetime=start + timedelta(hours=1),
        )

    def _message_texts(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class FreeTierGateTest(GateFixture):
    tier = "free"

    # --- Sperrzeiten ----------------------------------------------------------

    def test_cannot_create_blocked_time(self):
        response = self.client.get(reverse("blocked_times:create"))

        self.assertRedirects(response, reverse("lessons:calendar"), fetch_redirect_response=False)
        self.assertIn(
            "Sperrzeiten gibt es ab dem Starter-Tarif", " ".join(self._message_texts(response))
        )

    def test_cannot_edit_but_can_delete_existing_blocked_time(self):
        bt = self._blocked_time()

        edit = self.client.get(reverse("blocked_times:update", kwargs={"pk": bt.pk}))
        self.assertEqual(edit.status_code, 302)

        self.client.post(reverse("blocked_times:delete", kwargs={"pk": bt.pk}))
        self.assertFalse(BlockedTime.objects.filter(pk=bt.pk).exists())

    # --- Serien ---------------------------------------------------------------

    def test_cannot_create_or_edit_series(self):
        series = self._series()
        for url in (
            reverse("lessons:recurring_create"),
            reverse("lessons:recurring_update", kwargs={"pk": series.pk}),
            reverse("lessons:recurring_bulk_edit"),
        ):
            with self.subTest(url=url):
                self.assertRedirects(
                    self.client.get(url),
                    reverse("lessons:recurring_list"),
                    fetch_redirect_response=False,
                )

    def test_cannot_generate_lessons_from_series(self):
        series = self._series()

        self.client.post(reverse("lessons:recurring_generate", kwargs={"pk": series.pk}))

        self.assertFalse(Session.objects.filter(contract=self.contract).exists())

    def test_can_still_view_and_delete_existing_series(self):
        series = self._series()

        self.assertEqual(self.client.get(reverse("lessons:recurring_list")).status_code, 200)
        detail = self.client.get(reverse("lessons:recurring_detail", kwargs={"pk": series.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(
            detail, reverse("lessons:recurring_generate", kwargs={"pk": series.pk})
        )
        self.client.post(reverse("lessons:recurring_delete", kwargs={"pk": series.pk}))
        self.assertFalse(RecurringSession.objects.filter(pk=series.pk).exists())

    def test_lesson_form_cannot_smuggle_in_a_series(self):
        """Das Häkchen 'wiederkehrend' ist gesperrt - auch wenn es jemand mitschickt."""
        response = self.client.post(
            reverse("lessons:create"),
            {
                "contract": self.contract.pk,
                "date": date.today() + timedelta(days=7),
                "start_time": "14:00",
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "notes": "",
                "is_recurring": "on",
                "recurrence_type": "weekly",
                "recurrence_weekdays": ["0", "2"],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(RecurringSession.objects.filter(contract=self.contract).exists())
        self.assertEqual(Session.objects.filter(contract=self.contract).count(), 1)

    def test_lesson_form_hides_the_series_section(self):
        page = self.client.get(reverse("lessons:create"))

        self.assertNotContains(page, 'id="recurrence-section"')

    # --- Schüler-Portal -------------------------------------------------------

    def test_cannot_invite_to_portal(self):
        response = self.client.post(
            reverse("students:portal_invite", kwargs={"pk": self.contract.pk}),
            {"email": "lea@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("contracts:detail", kwargs={"pk": self.contract.pk}),
            fetch_redirect_response=False,
        )
        self.assertFalse(ParentStudentLink.objects.filter(contract=self.contract).exists())

    def test_existing_portal_account_keeps_working(self):
        """Läuft ein Abo aus, verlieren Schüler und Eltern ihren Zugang nicht."""
        user = User.objects.create_user(
            username="p1", password="geheim-123", email="lea@example.com"
        )
        portal_user = PortalUser.objects.create(user=user, role="student", tutor=self.tutor)
        ParentStudentLink.objects.create(parent=portal_user, contract=self.contract, is_active=True)
        self.client.logout()

        response = self.client.post(
            reverse("portal:login"), {"email": "lea@example.com", "password": "geheim-123"}
        )

        self.assertRedirects(response, reverse("portal:home"), fetch_redirect_response=False)

    def test_contract_page_shows_hint_instead_of_invite_form(self):
        page = self.client.get(reverse("contracts:detail", kwargs={"pk": self.contract.pk}))

        self.assertContains(page, "Das Schüler-Portal gibt es ab dem Starter-Tarif")
        self.assertNotContains(
            page, reverse("students:portal_invite", kwargs={"pk": self.contract.pk})
        )


class StarterTierGateTest(GateFixture):
    tier = "starter"

    def test_blocked_times_and_series_available(self):
        self.assertEqual(self.client.get(reverse("blocked_times:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("lessons:recurring_create")).status_code, 200)
        self.assertContains(self.client.get(reverse("lessons:create")), 'id="recurrence-section"')

    def test_portal_invite_available(self):
        page = self.client.get(reverse("contracts:detail", kwargs={"pk": self.contract.pk}))

        self.assertContains(
            page, reverse("students:portal_invite", kwargs={"pk": self.contract.pk})
        )

    def test_second_child_with_same_email_is_not_linked(self):
        """Familien-Zugang (mehrere Kinder an einem Konto) erst ab Pro."""
        user = User.objects.create_user(username="fam", password="x", email="familie@example.com")
        account = PortalUser.objects.create(user=user, role="student", tutor=self.tutor)
        ParentStudentLink.objects.create(parent=account, contract=self.contract, is_active=True)
        sibling = self._contract("Max", "familie@example.com")

        response = self.client.post(
            reverse("students:portal_invite", kwargs={"pk": sibling.pk}),
            {"email": "familie@example.com"},
        )

        self.assertFalse(ParentStudentLink.objects.filter(contract=sibling).exists())
        self.assertIn("Familien-Zugang", " ".join(self._message_texts(response)))

    def test_family_link_button_is_blocked(self):
        sibling = self._contract("Max", "lea@example.com")

        response = self.client.post(
            reverse("students:link_family", kwargs={"pk": self.contract.pk, "other_pk": sibling.pk})
        )

        self.assertRedirects(response, reverse("contracts:list"), fetch_redirect_response=False)
        self.assertIn("Familien-Zugang", " ".join(self._message_texts(response)))

    def test_cannot_start_meeting(self):
        lesson = Session.objects.create(
            contract=self.contract, date=date.today(), start_time=time(15, 0), duration_minutes=60
        )

        response = self.client.post(reverse("meeting:start", kwargs={"lesson_pk": lesson.pk}))

        self.assertRedirects(
            response,
            reverse("lessons:detail", kwargs={"pk": lesson.pk}),
            fetch_redirect_response=False,
        )
        self.assertFalse(MeetingRoom.objects.filter(lesson=lesson).exists())
        detail = self.client.get(reverse("lessons:detail", kwargs={"pk": lesson.pk}))
        self.assertNotContains(detail, reverse("meeting:start", kwargs={"lesson_pk": lesson.pk}))


class ProTierGateTest(GateFixture):
    tier = "pro"

    def test_second_child_with_same_email_is_linked(self):
        user = User.objects.create_user(username="fam", password="x", email="familie@example.com")
        account = PortalUser.objects.create(user=user, role="student", tutor=self.tutor)
        ParentStudentLink.objects.create(parent=account, contract=self.contract, is_active=True)
        sibling = self._contract("Max", "familie@example.com")

        self.client.post(
            reverse("students:portal_invite", kwargs={"pk": sibling.pk}),
            {"email": "familie@example.com"},
        )

        self.assertTrue(ParentStudentLink.objects.filter(parent=account, contract=sibling).exists())

    def test_can_start_meeting(self):
        lesson = Session.objects.create(
            contract=self.contract, date=date.today(), start_time=time(15, 0), duration_minutes=60
        )

        self.client.post(reverse("meeting:start", kwargs={"lesson_pk": lesson.pk}))

        self.assertTrue(MeetingRoom.objects.filter(lesson=lesson, is_active=True).exists())
