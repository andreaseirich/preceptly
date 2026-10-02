"""Portal: abgesagte Termine bleiben nachvollziehbar, der Tutor wird benachrichtigt.

Anlass 02.10.2026: Eine Absage im Portal löschte die Stunde spurlos, und der
Tutor erfuhr weder davon noch von einer Verschiebung."""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import NotificationPreference, UserProfile
from apps.lessons.models import CancelledSession, Session
from apps.lessons.recurring_models import RecurringSession
from apps.portal.models import ParentStudentLink, PortalUser


class PortalChangeFixture(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(
            username="tutor_cancel", password="pass", email="tutor@example.com"
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
        self.account = PortalUser.objects.create(
            user=User.objects.create_user(
                username="portal_cancel", password="pass", email="lea@example.com"
            ),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(
            parent=self.account, contract=self.contract, is_active=True
        )
        session = self.client.session
        session["portal_user_id"] = self.account.pk
        session.save()
        self.day = date.today() + timedelta(days=3)
        mail.outbox.clear()

    def lesson(self, day=None, **extra):
        fields = {
            "contract": self.contract,
            "date": day or self.day,
            "start_time": time(16, 0),
            "duration_minutes": 60,
            "status": "planned",
            "created_via": "portal_booking",
            "booked_by": self.account.user,
        }
        fields.update(extra)
        return Session.objects.create(**fields)

    def cancel(self, lesson):
        return self.client.post(reverse("portal:session_cancel", args=[lesson.pk]))


class CancelTest(PortalChangeFixture):
    def test_cancelled_lesson_leaves_the_calendar_but_stays_on_record(self):
        lesson = self.lesson()
        booked_at = lesson.created_at

        self.cancel(lesson)

        self.assertFalse(Session.objects.filter(pk=lesson.pk).exists())
        record = CancelledSession.objects.get(contract=self.contract)
        self.assertEqual((record.date, record.start_time), (self.day, time(16, 0)))
        self.assertEqual(record.cancelled_by, self.account.user)
        self.assertEqual(record.cancelled_via, CancelledSession.VIA_PORTAL)
        self.assertEqual(record.booked_by, self.account.user)
        self.assertEqual(record.booked_at, booked_at)
        self.assertFalse(record.was_series)

    def test_tutor_gets_a_mail(self):
        self.cancel(self.lesson())

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["tutor@example.com"])
        self.assertIn("Termin abgesagt: Lea Schmidt", message.subject)
        self.assertIn("16:00 Uhr (60 Min.)", message.body)
        self.assertIn("über das Portal vom Schülerkonto (lea@example.com)", message.body)

    def test_no_mail_when_the_tutor_switched_it_off(self):
        NotificationPreference.objects.create(user=self.tutor, notify_portal_change_email=False)

        self.cancel(self.lesson())

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(CancelledSession.objects.count(), 1)

    def test_only_planned_lessons_can_be_cancelled(self):
        taught = self.lesson(day=date.today() - timedelta(days=2), status="taught")

        self.cancel(taught)

        self.assertTrue(Session.objects.filter(pk=taught.pk).exists())
        self.assertEqual(CancelledSession.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_freed_slot_can_be_booked_again(self):
        self.cancel(self.lesson())

        self.client.post(
            reverse("portal:book", kwargs={"student_pk": self.contract.pk}),
            {"date": self.day.isoformat(), "start_time": "16:00"},
        )

        self.assertEqual(Session.objects.filter(contract=self.contract, date=self.day).count(), 1)

    def test_other_families_cannot_cancel(self):
        lesson = self.lesson()
        stranger = PortalUser.objects.create(
            user=User.objects.create_user(username="portal_other", password="pass"),
            role="student",
            tutor=self.tutor,
        )
        session = self.client.session
        session["portal_user_id"] = stranger.pk
        session.save()

        response = self.cancel(lesson)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Session.objects.filter(pk=lesson.pk).exists())
        self.assertEqual(CancelledSession.objects.count(), 0)


class RescheduleTest(PortalChangeFixture):
    def test_tutor_learns_old_and_new_time(self):
        lesson = self.lesson()
        new_day = self.day + timedelta(days=1)

        self.client.post(
            reverse("portal:session_reschedule", args=[lesson.pk]),
            {"date": new_day.isoformat(), "start_time": "17:00"},
        )

        lesson.refresh_from_db()
        self.assertEqual((lesson.date, lesson.start_time), (new_day, time(17, 0)))
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Termin verschoben: Lea Schmidt", mail.outbox[0].subject)
        self.assertIn("Bisher:", body)
        self.assertIn(self.day.strftime("%d.%m.%Y") + ", 16:00 Uhr", body)
        self.assertIn(new_day.strftime("%d.%m.%Y") + ", 17:00 Uhr (60 Min.)", body)
        # verschoben ist nicht abgesagt
        self.assertEqual(CancelledSession.objects.count(), 0)


class SeriesCancelTest(PortalChangeFixture):
    def test_every_future_lesson_of_the_series_is_kept_on_record(self):
        series = RecurringSession.objects.create(
            contract=self.contract,
            start_date=date.today() - timedelta(days=14),
            start_time=time(16, 0),
            duration_minutes=60,
            recurrence_type="weekly",
            monday=True,
            is_active=True,
        )
        past = self.lesson(
            day=date.today() - timedelta(days=7), status="taught", recurring_session=series
        )
        future = [
            self.lesson(day=date.today() + timedelta(days=offset), recurring_session=series)
            for offset in (7, 14, 21)
        ]

        self.client.post(reverse("portal:recurring_cancel", args=[series.pk]))

        series.refresh_from_db()
        self.assertFalse(series.is_active)
        self.assertTrue(Session.objects.filter(pk=past.pk).exists())
        self.assertFalse(Session.objects.filter(pk__in=[s.pk for s in future]).exists())
        records = CancelledSession.objects.filter(contract=self.contract)
        self.assertEqual(records.count(), 3)
        for record in records:
            self.assertEqual(record.cancelled_via, CancelledSession.VIA_PORTAL_SERIES)
            self.assertTrue(record.was_series)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Serie beendet: Lea Schmidt", mail.outbox[0].subject)
        self.assertIn("Mo, 16:00 Uhr", mail.outbox[0].body)
        self.assertIn("Entfallene Termine: 3 (", mail.outbox[0].body)


class OverviewTest(PortalChangeFixture):
    def test_family_and_tutor_see_who_cancelled(self):
        self.cancel(self.lesson())

        portal_page = self.client.get(reverse("portal:student_lessons"))
        self.assertContains(portal_page, "Abgesagte Termine")
        self.assertContains(portal_page, "über das Portal von dir")
        self.assertNotContains(portal_page, "lea@example.com")

        self.client.force_login(self.tutor)
        tutor_page = self.client.get(reverse("contracts:detail", args=[self.contract.pk]))
        self.assertContains(tutor_page, "Im Portal abgesagte Termine")
        self.assertContains(tutor_page, "über das Portal vom Schülerkonto (lea@example.com)")

    def test_nothing_shown_without_cancellations(self):
        self.lesson()

        self.assertNotContains(
            self.client.get(reverse("portal:student_lessons")), "Abgesagte Termine"
        )
        self.client.force_login(self.tutor)
        self.assertNotContains(
            self.client.get(reverse("contracts:detail", args=[self.contract.pk])),
            "Im Portal abgesagte Termine",
        )


class NotificationSettingsTest(PortalChangeFixture):
    def test_tutor_can_switch_the_new_notifications(self):
        self.client.force_login(self.tutor)
        url = reverse("core:settings")

        self.assertContains(self.client.get(url), 'name="notify_portal_change_email"')

        self.client.post(url, {"save_notifications": "1", "notify_portal_booking_email": "on"})
        pref = NotificationPreference.objects.get(user=self.tutor)
        self.assertTrue(pref.notify_portal_booking_email)
        self.assertFalse(pref.notify_portal_change_email)
        self.assertFalse(pref.notify_portal_change_push)

        self.client.post(
            url,
            {
                "save_notifications": "1",
                "notify_portal_change_email": "on",
                "notify_portal_change_push": "on",
            },
        )
        pref.refresh_from_db()
        self.assertTrue(pref.notify_portal_change_email)
        self.assertTrue(pref.notify_portal_change_push)
