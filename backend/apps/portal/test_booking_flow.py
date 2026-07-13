"""
Integrationstest: Portal-Buchung, belegte Zeiten, Tutor-Kalender.
Ausführen: python manage.py test apps.portal.test_booking_flow --verbosity=2
"""

import datetime as dt
from decimal import Decimal

import django.utils.timezone as tz
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Session
from apps.portal.models import PortalUser, StudentPortalLink

User = get_user_model()


class PortalBookingFlowTest(TestCase):
    def setUp(self):
        # Tutor
        self.tutor = User.objects.create_user(
            username="flow_tutor", password="pass", email="tutor@flow.test"
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.tutor)

        self.test_date = dt.date.today() + dt.timedelta(days=1)
        day_name = self.test_date.strftime("%A").lower()
        self.profile.default_working_hours = {day_name: [{"start": "08:00", "end": "20:00"}]}
        self.profile.save()

        # Schülervertrag
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Testschüler",
            last_name="Portal",
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )

        # Anderer Schüler — belegt 10:00–11:00
        contract2 = Contract.objects.create(
            user=self.tutor,
            first_name="Anderer",
            last_name="Schüler",
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )
        Session.objects.create(
            contract=contract2,
            date=self.test_date,
            start_time=dt.time(10, 0),
            duration_minutes=60,
            status="planned",
        )

        # BlockedTime: 14:00–15:00
        BlockedTime.objects.create(
            user=self.tutor,
            title="Arzttermin",
            start_datetime=tz.make_aware(dt.datetime.combine(self.test_date, dt.time(14, 0))),
            end_datetime=tz.make_aware(dt.datetime.combine(self.test_date, dt.time(15, 0))),
        )

        # Portal-User (Schüler-Account)
        portal_django_user = User.objects.create_user(
            username="flow_student_portal", password="pass"
        )
        self.portal_user = PortalUser.objects.create(
            user=portal_django_user,
            tutor=self.tutor,
            role="student",
        )
        StudentPortalLink.objects.create(
            portal_user=self.portal_user,
            contract=self.contract,
            is_active=True,
        )

        # Portal-Session setzen (wie nach Login)
        self.c = Client()
        s = self.c.session
        s["portal_user_id"] = self.portal_user.pk
        s.save()

    # ------------------------------------------------------------------
    def test_1_availability_free_and_busy_slots(self):
        """10:00 (Session) und 14:00 (BlockedTime) sind nicht buchbar; 09:00 ist frei."""
        url = f"/portal/availability/{self.contract.pk}/?date={self.test_date.isoformat()}"
        resp = self.c.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        slots = data["slots"]
        busy_starts = [b["start"] for b in data["busy_slots"]]

        self.assertNotIn("10:00", slots, "10:00 muss gesperrt sein (fremde Session)")
        self.assertNotIn("14:00", slots, "14:00 muss gesperrt sein (BlockedTime)")
        self.assertIn("09:00", slots, "09:00 muss frei sein")
        self.assertIn("10:00", busy_starts, "10:00 muss in busy_slots erscheinen")
        self.assertIn("14:00", busy_starts, "14:00 muss in busy_slots erscheinen")

    # ------------------------------------------------------------------
    def test_2_booking_free_slot_creates_session(self):
        """Buchung auf 09:00 legt Session mit created_via=portal_booking an."""
        resp = self.c.post(
            f"/portal/book/{self.contract.pk}/",
            {
                "date": self.test_date.isoformat(),
                "start_time": "09:00",
                "topic": "Algebra",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "gebucht")

        session = Session.objects.filter(
            contract=self.contract, date=self.test_date, start_time=dt.time(9, 0)
        ).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.created_via, "portal_booking")
        self.assertEqual(session.notes, "Algebra")

    # ------------------------------------------------------------------
    def test_3_booking_busy_session_rejected(self):
        """Buchung auf 10:00 (fremde Session) wird abgelehnt."""
        resp = self.c.post(
            f"/portal/book/{self.contract.pk}/",
            {
                "date": self.test_date.isoformat(),
                "start_time": "10:00",
                "topic": "Konflikt",
            },
        )
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertTrue(
            "Zeitkonflikt" in content or "belegt" in content.lower(),
            f"Erwarte Fehlermeldung, bekam: {content[:200]}",
        )
        self.assertIsNone(
            Session.objects.filter(
                contract=self.contract, date=self.test_date, start_time=dt.time(10, 0)
            ).first()
        )

    # ------------------------------------------------------------------
    def test_4_booking_blocked_time_rejected(self):
        """Buchung auf 14:00 (BlockedTime) wird abgelehnt."""
        self.c.post(
            f"/portal/book/{self.contract.pk}/",
            {
                "date": self.test_date.isoformat(),
                "start_time": "14:00",
                "topic": "BT-Test",
            },
        )
        self.assertIsNone(
            Session.objects.filter(
                contract=self.contract, date=self.test_date, start_time=dt.time(14, 0)
            ).first()
        )

    # ------------------------------------------------------------------
    def test_5_calendar_shows_busy_entries(self):
        """Monatskalender enthält anonymisierte belegte Blöcke."""
        resp = self.c.get(
            f"/portal/calendar/?year={self.test_date.year}&month={self.test_date.month}"
        )
        self.assertEqual(resp.status_code, 200)
        weeks = resp.context["weeks"]
        day_data = next((d for w in weeks for d in w if d and d["date"] == self.test_date), None)
        self.assertIsNotNone(day_data)
        busy_non_own = [e for e in day_data.get("busy", []) if not e["is_own"]]
        self.assertGreaterEqual(
            len(busy_non_own), 1, f"Fremde Blöcke fehlen in busy: {day_data.get('busy')}"
        )

    # ------------------------------------------------------------------
    def test_6_booked_session_in_tutor_db(self):
        """Nach Buchung ist die Session in den Tutor-Sessions sichtbar."""
        self.c.post(
            f"/portal/book/{self.contract.pk}/",
            {
                "date": self.test_date.isoformat(),
                "start_time": "09:00",
                "topic": "Test",
            },
        )
        session = Session.objects.filter(
            contract__user=self.tutor,
            contract=self.contract,
            date=self.test_date,
            start_time=dt.time(9, 0),
        ).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.created_via, "portal_booking")

    # ------------------------------------------------------------------
    def test_7_booking_page_get_renders_week_calendar(self):
        """Die Buchungsseite rendert die Wochenkalender-Auswahl (nicht nur eine Weiterleitung)."""
        resp = self.c.get(f"/portal/book/{self.contract.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "week-day-pick")

    def test_8_reschedule_page_get_renders_week_calendar(self):
        """Die Verschieben-Seite rendert die Wochenkalender-Auswahl."""
        session = Session.objects.create(
            contract=self.contract,
            date=self.test_date,
            start_time=dt.time(9, 0),
            duration_minutes=60,
            status="planned",
        )
        resp = self.c.get(f"/portal/session/{session.pk}/reschedule/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "week-day-pick")
