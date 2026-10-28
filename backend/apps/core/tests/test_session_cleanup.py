"""Abgelaufene Login-Sitzungen automatisch löschen, ohne dass andere Funktionen darunter leiden.

Auftrag von Andreas, 28.10.2026: "Die abgelaufenen Sessions könnten gelöscht werden, aber man sollte vorher prüfen, ob alle
anderen Funktionen dann trotzdem noch gut laufen (z. B. Rechnungen, Steuern, etc.)."

Achtung, zwei verschiedene "Session": Gelöscht werden die Login-Sitzungen von Django (django_session), hier LoginSession.
Die Stunden (apps.lessons.models.Session, hier Lesson) bleiben unberührt, an ihnen hängen Rechnungen und Steuern.
"""

import datetime as dt
from datetime import date, time
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session as LoginSession
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.core.middleware import _PURGE_CACHE_KEY
from apps.core.models import Expense, RequestLog
from apps.core.session_cleanup import purge_expired_sessions
from apps.lessons.models import Lesson
from apps.portal.models import ParentStudentLink, PortalUser


def make_login_session(key, expires_in_days):
    """Eine Login-Sitzung mit fester Gültigkeit (negativ: schon abgelaufen). Der Inhalt wird bei abgelaufenen nie gelesen."""
    return LoginSession.objects.create(
        session_key=key.ljust(32, "x")[:32],
        session_data="x",
        expire_date=timezone.now() + dt.timedelta(days=expires_in_days),
    )


class PurgeTest(TestCase):
    def test_only_expired_sessions_are_deleted(self):
        expired = [make_login_session(f"old{i}", -1 - i) for i in range(3)]
        valid = [make_login_session("new1", 1), make_login_session("new2", 13)]

        deleted = purge_expired_sessions()

        self.assertEqual(deleted, 3)
        self.assertFalse(LoginSession.objects.filter(pk__in=[s.pk for s in expired]).exists())
        self.assertEqual(LoginSession.objects.filter(pk__in=[s.pk for s in valid]).count(), 2)

    def test_a_session_that_ends_a_moment_ago_goes_one_that_ends_in_a_moment_stays(self):
        gone = LoginSession.objects.create(
            session_key="a" * 32,
            session_data="x",
            expire_date=timezone.now() - dt.timedelta(seconds=1),
        )
        stays = LoginSession.objects.create(
            session_key="b" * 32,
            session_data="x",
            expire_date=timezone.now() + dt.timedelta(minutes=5),
        )

        purge_expired_sessions()

        self.assertFalse(LoginSession.objects.filter(pk=gone.pk).exists())
        self.assertTrue(LoginSession.objects.filter(pk=stays.pk).exists())

    def test_running_it_again_deletes_nothing(self):
        make_login_session("old", -1)

        self.assertEqual(purge_expired_sessions(), 1)
        self.assertEqual(purge_expired_sessions(), 0)

    def test_an_empty_table_is_fine(self):
        self.assertEqual(purge_expired_sessions(), 0)


class BusinessFixture(TestCase):
    """Ein Tutor mit Schüler, unterrichteter Stunde, Rechnung und Ausgabe, angemeldet mit gültiger Sitzung."""

    def setUp(self):
        cache.clear()
        # Sperre für den Tag setzen: Die Seitenaufrufe in den Tests räumen nicht von selbst auf, aufgeräumt wird
        # nur dort, wo der Test es ausdrücklich tut (DailyPurgeTest hebt die Sperre auf).
        cache.set(_PURGE_CACHE_KEY, "1", 24 * 60 * 60)
        self.user = User.objects.create_user(username="tutor_clean", password="testpass123")
        self.client = Client()
        self.client.force_login(self.user)
        self.contract = Contract.objects.create(
            user=self.user,
            first_name="Test",
            last_name="Schüler",
            hourly_rate=Decimal("30"),
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
        )
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 3, 5),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )
        self.invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 3, 1), date(2025, 3, 31), contract=self.contract, user=self.user
        )
        Expense.objects.create(
            user=self.user,
            date="2025-03-05",
            amount=Decimal("50.00"),
            category="office",
            description="Büromaterial",
            business_use_percent=100,
        )
        # Viele abgelaufene Sitzungen anderer Besucher in der Tabelle, wie in der Produktion
        for index in range(20):
            make_login_session(f"expired{index}", -1 - index)

    def counts(self):
        return {
            "Stunden": Lesson.objects.count(),
            "Verträge": Contract.objects.count(),
            "Rechnungen": Invoice.objects.count(),
            "Ausgaben": Expense.objects.count(),
            "Zugriffsprotokoll": RequestLog.objects.count(),
        }


class BusinessFunctionsAfterCleanupTest(BusinessFixture):
    PAGES = (
        ("Dashboard", "core:dashboard", None, {}),
        ("Rechnungsliste", "billing:invoice_list", None, {}),
        ("Rechnung", "billing:invoice_detail", "invoice", {}),
        ("Einnahmen", "core:income", None, {}),
        ("Steuerjahr", "core:tax_year", None, {"year": 2025}),
        ("EÜR", "core:euer", None, {"year": 2025}),
    )

    def url(self, name, which):
        return reverse(name, args=[self.invoice.pk]) if which == "invoice" else reverse(name)

    def test_every_page_behaves_the_same_before_and_after_the_cleanup(self):
        before = {
            label: self.client.get(self.url(name, which), params).status_code
            for label, name, which, params in self.PAGES
        }

        deleted = purge_expired_sessions()
        after = {
            label: self.client.get(self.url(name, which), params).status_code
            for label, name, which, params in self.PAGES
        }

        self.assertEqual(deleted, 20)
        self.assertEqual(before, after)
        self.assertTrue(all(code == 200 for code in after.values()), after)

    def test_the_tax_pdf_still_works(self):
        purge_expired_sessions()

        response = self.client.get(reverse("core:euer_pdf"), {"year": 2025})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_lessons_invoices_and_expenses_are_untouched(self):
        before = self.counts()
        total = Invoice.objects.get(pk=self.invoice.pk).total_amount

        purge_expired_sessions()

        self.assertEqual(self.counts(), before)
        self.assertEqual(Invoice.objects.get(pk=self.invoice.pk).total_amount, total)

    def test_the_signed_in_tutor_stays_signed_in(self):
        purge_expired_sessions()

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)  # keine Weiterleitung zur Anmeldung

    def test_a_new_invoice_can_still_be_created_afterwards(self):
        purge_expired_sessions()
        Lesson.objects.create(
            contract=self.contract,
            date=date(2025, 4, 2),
            start_time=time(14, 0),
            duration_minutes=60,
            status="taught",
        )

        invoice = InvoiceService.create_invoice_from_lessons(
            date(2025, 4, 1), date(2025, 4, 30), contract=self.contract, user=self.user
        )

        self.assertEqual(Invoice.objects.filter(owner=self.user).count(), 2)
        self.assertEqual(invoice.total_amount, Decimal("30.00"))

    def test_request_logs_keep_their_hash_of_the_session_key(self):
        RequestLog.objects.create(path="/x/", method="GET", status_code=200, session_key="a" * 40)

        purge_expired_sessions()

        self.assertEqual(RequestLog.objects.filter(session_key="a" * 40).count(), 1)


class ExpiredAndPortalSessionsTest(BusinessFixture):
    def test_an_expired_login_behaves_the_same_with_or_without_its_row(self):
        key = self.client.session.session_key
        LoginSession.objects.filter(session_key=key).update(
            expire_date=timezone.now() - dt.timedelta(days=1)
        )
        url = reverse("core:dashboard")

        before = self.client.get(url)
        purge_expired_sessions()
        after = self.client.get(url)

        self.assertFalse(LoginSession.objects.filter(session_key=key).exists())
        self.assertEqual(before.status_code, 302)  # abgelaufen: zur Anmeldung
        self.assertEqual((after.status_code, after["Location"]), (302, before["Location"]))

    def test_a_portal_login_survives_and_the_booking_page_still_opens(self):
        account = PortalUser.objects.create(
            user=User.objects.create_user(username="portal_clean", password="pass"),
            role="student",
            tutor=self.user,
        )
        ParentStudentLink.objects.create(parent=account, contract=self.contract, is_active=True)
        portal = Client()
        session = portal.session
        session["portal_user_id"] = account.pk
        session.save()
        url = reverse("portal:book", args=[self.contract.pk])
        before = portal.get(url).status_code

        purge_expired_sessions()
        after = portal.get(url).status_code

        self.assertEqual((before, after), (200, 200))


class DailyPurgeTest(BusinessFixture):
    def setUp(self):
        super().setUp()
        cache.delete(_PURGE_CACHE_KEY)
        LoginSession.objects.filter(session_key__startswith="expired").delete()

    def expired_rows(self):
        return LoginSession.objects.filter(expire_date__lt=timezone.now()).count()

    def test_the_first_request_of_the_day_cleans_up_and_later_ones_do_not(self):
        make_login_session("stale1", -3)

        self.client.get(reverse("core:landing"))
        self.assertEqual(self.expired_rows(), 0)

        make_login_session("stale2", -3)
        self.client.get(reverse("core:landing"))
        self.assertEqual(self.expired_rows(), 1)  # Sperre für den Tag: noch nicht wieder

        cache.delete(_PURGE_CACHE_KEY)  # nächster Tag
        self.client.get(reverse("core:landing"))
        self.assertEqual(self.expired_rows(), 0)

    def test_the_cleanup_never_logs_anyone_out(self):
        make_login_session("stale", -3)

        self.client.get(reverse("core:landing"))
        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_a_failing_session_cleanup_does_not_break_the_response_or_the_log_cleanup(self):
        old = RequestLog.objects.create(path="/alt/", method="GET", status_code=200)
        RequestLog.objects.filter(pk=old.pk).update(
            timestamp=timezone.now() - dt.timedelta(days=45)
        )

        with mock.patch(
            "apps.core.middleware.purge_expired_sessions", side_effect=RuntimeError("kaputt")
        ):
            response = Client().get(
                reverse("core:landing")
            )  # anonym: Angemeldete werden weitergeleitet

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            RequestLog.objects.filter(pk=old.pk).exists()
        )  # Protokoll trotzdem aufgeräumt

    def test_a_failing_log_cleanup_does_not_stop_the_session_cleanup(self):
        make_login_session("stale", -3)

        with mock.patch(
            "apps.core.middleware.purge_old_request_logs", side_effect=RuntimeError("kaputt")
        ):
            response = Client().get(reverse("core:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.expired_rows(), 0)
