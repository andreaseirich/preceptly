"""Wann und von wem eine Stunde gebucht wurde (seit 29.09.2026).

Anlass: Ein Schüler bestritt eine Portal-Buchung, und niemand konnte
nachsehen, welches Konto sie angelegt hatte."""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contracts.models import Contract
from apps.core.feature_flags import get_portal_booking_count_this_month
from apps.core.models import UserProfile
from apps.lessons.booking_origin import PORTAL, TUTOR, booking_origin
from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession
from apps.portal.models import ParentStudentLink, PortalUser


class BookingOriginTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(
            username="tutor_origin", password="pass", first_name="Andrea", last_name="Lehrer"
        )
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date.today() - timedelta(days=30),
        )
        self.student_account = self._portal_account("student", "lea@example.com")

    def _portal_account(self, role, email):
        user = User.objects.create_user(username=f"portal_{role}", password="pass", email=email)
        account = PortalUser.objects.create(user=user, role=role, tutor=self.tutor)
        ParentStudentLink.objects.create(parent=account, contract=self.contract, is_active=True)
        return account

    def _as_portal(self, account):
        self.client.logout()
        session = self.client.session
        session["portal_user_id"] = account.pk
        session.save()

    def _as_tutor(self):
        self.client.force_login(self.tutor)

    def _tutor_page(self, lesson):
        self._as_tutor()
        return self.client.get(reverse("lessons:detail", args=[lesson.pk]))

    def _portal_page(self, lesson, account=None, **headers):
        self._as_portal(account or self.student_account)
        return self.client.get(reverse("portal:student_lesson_detail", args=[lesson.pk]), **headers)

    def _stamp(self, lesson):
        return timezone.localtime(lesson.created_at).strftime("%d.%m.%Y, %H:%M")

    def _next_monday(self):
        today = date.today()
        return today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    # --- Portal -------------------------------------------------------------------

    def test_portal_booking_records_the_account(self):
        self._as_portal(self.student_account)
        self.client.post(
            reverse("portal:book", kwargs={"student_pk": self.contract.pk}),
            {"date": (date.today() + timedelta(days=3)).isoformat(), "start_time": "16:00"},
        )
        lesson = Session.objects.get(contract=self.contract)

        self.assertEqual(lesson.booked_by, self.student_account.user)
        self.assertEqual(lesson.created_via, "portal_booking")
        tutor_page = self._tutor_page(lesson)
        self.assertContains(tutor_page, self._stamp(lesson))
        self.assertContains(tutor_page, "über das Portal vom Schülerkonto (lea@example.com)")
        self.assertContains(self._portal_page(lesson), "über das Portal von dir")

    def test_family_sees_other_accounts_without_email(self):
        parent = self._portal_account("parent", "mama@example.com")
        lesson = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=2),
            start_time=time(15, 0),
            duration_minutes=60,
            status="planned",
            created_via="portal_booking",
            booked_by=parent.user,
        )

        page = self._portal_page(lesson)

        self.assertContains(page, "über das Portal vom Elternkonto")
        self.assertNotContains(page, "mama@example.com")
        self.assertContains(self._tutor_page(lesson), "vom Elternkonto (mama@example.com)")

    def test_portal_series_lessons_carry_the_account(self):
        self._as_portal(self.student_account)
        monday = self._next_monday()
        self.client.post(
            reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk}),
            {
                "start_time": "16:00",
                "start_date": monday.isoformat(),
                "end_date": (monday + timedelta(days=14)).isoformat(),
                "monday": "on",
            },
        )
        series = RecurringSession.objects.get(contract=self.contract)
        lessons = Session.objects.filter(recurring_session=series)

        self.assertEqual(series.booked_by, self.student_account.user)
        self.assertEqual(lessons.count(), 3)
        for lesson in lessons:
            self.assertEqual(lesson.booked_by, self.student_account.user)
            self.assertEqual(lesson.created_via, "portal_series")
        self.assertContains(
            self._tutor_page(lessons[0]), "als Serie über das Portal vom Schülerkonto"
        )
        # Serien zählen weiterhin nicht als Einzelbuchungen fürs Monatslimit
        self.assertEqual(get_portal_booking_count_this_month(self.tutor), 0)

    def test_portal_page_stays_german_for_english_browsers(self):
        lesson = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=2),
            start_time=time(15, 0),
            duration_minutes=60,
            status="planned",
            created_via="portal_booking",
            booked_by=self.student_account.user,
        )

        page = self._portal_page(lesson, HTTP_ACCEPT_LANGUAGE="en")

        self.assertContains(page, "über das Portal von dir")

    # --- Tutor --------------------------------------------------------------------

    def _tutor_form(self, **extra):
        data = {
            "contract": self.contract.pk,
            "date": self._next_monday(),
            "start_time": time(14, 0),
            "duration_minutes": 60,
            "travel_time_before_minutes": 0,
            "travel_time_after_minutes": 0,
            "notes": "",
        }
        data.update(extra)
        return data

    def test_tutor_lesson_records_the_tutor(self):
        self._as_tutor()
        self.client.post(reverse("lessons:create"), self._tutor_form())
        lesson = Session.objects.get(contract=self.contract)

        self.assertEqual(lesson.booked_by, self.tutor)
        self.assertEqual(lesson.created_via, "tutor")
        self.assertContains(self._tutor_page(lesson), "von dir")
        self.assertContains(self._portal_page(lesson), "von Andrea Lehrer")

    def test_tutor_series_from_the_lesson_form(self):
        self._as_tutor()
        monday = self._next_monday()
        self.client.post(
            reverse("lessons:create"),
            self._tutor_form(
                is_recurring=True,
                recurrence_type="weekly",
                recurrence_end_date=monday + timedelta(days=7),
                recurrence_weekdays=["0"],
            ),
        )
        lessons = Session.objects.filter(contract=self.contract)

        # zwei Montage, keine zusätzliche Einzelstunde am ersten Tag (Fehler bis 29.09.2026)
        self.assertEqual(lessons.count(), 2)
        for lesson in lessons:
            self.assertEqual(lesson.booked_by, self.tutor)
            self.assertEqual(lesson.created_via, "tutor")
        self.assertContains(self._tutor_page(lessons[0]), "als Teil einer Serie von dir")

    def test_tutor_series_from_the_series_form(self):
        self._as_tutor()
        monday = self._next_monday()
        self.client.post(
            reverse("lessons:recurring_create"),
            {
                "contract": self.contract.pk,
                "start_date": monday,
                "end_date": monday + timedelta(days=7),
                "start_time": time(10, 0),
                "duration_minutes": 60,
                "travel_time_before_minutes": 0,
                "travel_time_after_minutes": 0,
                "recurrence_type": "weekly",
                "monday": True,
                "is_active": True,
                "notes": "",
            },
        )
        series = RecurringSession.objects.get(contract=self.contract)

        self.assertEqual(series.booked_by, self.tutor)
        self.assertTrue(Session.objects.filter(recurring_session=series).exists())
        for lesson in Session.objects.filter(recurring_session=series):
            self.assertEqual(lesson.booked_by, self.tutor)

    # --- Ältere Stunden -----------------------------------------------------------

    def test_older_lessons_show_time_and_channel_only(self):
        lesson = Session.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=2),
            start_time=time(15, 0),
            duration_minutes=60,
            status="planned",
            created_via="portal_booking",
        )

        for page in (self._tutor_page(lesson), self._portal_page(lesson)):
            self.assertContains(page, self._stamp(lesson))
            self.assertContains(page, "über das Portal")
            self.assertContains(page, "erst seit dem 29.09.2026 gespeichert")

    def test_accounts_without_portal_profile(self):
        admin = User.objects.create_user(username="admin_origin", password="pass")
        lesson = Session.objects.create(
            contract=self.contract,
            date=date.today(),
            start_time=time(9, 0),
            duration_minutes=60,
            status="planned",
            booked_by=admin,
        )

        origin = booking_origin(lesson, viewer=TUTOR)
        family_view = booking_origin(lesson, viewer=PORTAL, portal_user=self.student_account)

        self.assertEqual(origin.note, "")
        self.assertIn(origin.how, ("by another account", "von einem anderen Konto"))
        self.assertEqual(family_view.how, origin.how)
