"""Free-Tarif: Der Wortlaut der Oberfläche entspricht dem tatsächlichen Verhalten.

Befund vom 20.11.2026 (Prüfung der Aussage „wird durchgesetzt“): Die Grenzen sind **weich**. Beim 6. Schüler und bei der 9. Rechnung eines Kalendermonats zeigt
Preceptly einen Hinweis auf die bezahlten Tarife; gespeichert wird trotzdem, es wird nichts gesperrt (PRD, `free_limits.py`, `test_free_plan_limits.py`). Gezählt wird:
- Schüler: jeder Vertrag des Kontos, auch beendete oder inaktive (früher stand in der Meldung „aktive Schüler“),
- Rechnungen: jede im laufenden Kalendermonat (deutsche Zeit) angelegte Rechnung, unabhängig vom Zeitraum der Stunden; Stornorechnungen sind eigene Rechnungen und zählen mit.
Die Hinweise gelten nur für Free-Konten ab dem 02.07.2026.

Diese Tests halten Startseite, FAQ und Meldungen an diese Regeln und an die Konstanten in `feature_flags.py`.
"""

from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext

from apps.billing.models import Invoice
from apps.contracts.models import Contract
from apps.core.feature_flags import FREE_INVOICE_MONTHLY_LIMIT, FREE_STUDENT_LIMIT
from apps.core.free_limits import invoices_created_this_month


def get_in(client, name, lang):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
    return client.get(reverse(name))


class LandingFreeWordingTest(TestCase):
    def test_the_plan_is_called_free_in_both_languages(self):
        for lang in ("de", "en"):
            with self.subTest(sprache=lang):
                html = get_in(self.client, "core:landing", lang).content.decode()
                self.assertIn("<h3>Free</h3>", html)
                self.assertNotIn("Basic", html)
                self.assertNotIn("Kostenloser Tarif", html)
                self.assertNotIn("kostenlosen Tarif", html)

    def test_the_group_and_demo_labels_use_the_plan_name(self):
        html = get_in(self.client, "core:landing", "de").content.decode()

        self.assertIn("Im Free-Tarif enthalten", html)
        self.assertIn("Free-Tarif", html)  # Demo-Zugang

    def test_the_limits_are_called_a_guide_not_a_cap(self):
        de = get_in(self.client, "core:landing", "de").content.decode()
        en = get_in(self.client, "core:landing", "en").content.decode()

        self.assertIn(f"Gedacht für bis zu {FREE_STUDENT_LIMIT} Schüler", de)
        self.assertIn(f"Gedacht für bis zu {FREE_INVOICE_MONTHLY_LIMIT} Rechnungen im Monat", de)
        self.assertIn(f"Intended for up to {FREE_STUDENT_LIMIT} students", en)
        self.assertIn(f"Intended for up to {FREE_INVOICE_MONTHLY_LIMIT} invoices per month", en)
        self.assertNotIn(
            "Bis zu 5 Schüler", de, "„Bis zu“ klingt nach harter Grenze; es ist ein Hinweis"
        )

    def test_the_note_names_the_trigger_and_says_nothing_is_blocked(self):
        de = get_in(self.client, "core:landing", "de").content.decode()
        en = get_in(self.client, "core:landing", "en").content.decode()

        # Der Hinweis kommt ab dem (Limit + 1). Schüler und ab der (Limit + 1). Rechnung
        self.assertIn(
            f"ab dem {FREE_STUDENT_LIMIT + 1}. Schüler und ab der {FREE_INVOICE_MONTHLY_LIMIT + 1}. Rechnung",
            de,
        )
        self.assertIn("Es wird nichts gesperrt, alles wird gespeichert", de)
        self.assertIn("auch beendete", de)
        self.assertIn("auch Stornorechnungen", de)
        self.assertIn("Nothing is blocked and everything is saved", en)
        self.assertIn(
            f"from the {FREE_STUDENT_LIMIT + 1}th student and from the {FREE_INVOICE_MONTHLY_LIMIT + 1}th invoice",
            en,
        )

    def test_the_faq_uses_free_and_states_the_same_rules(self):
        html = self.client.get(reverse("core:faq")).content.decode()

        self.assertIn("Free (kostenlos):", html)
        self.assertNotIn("Basic (kostenlos)", html)
        self.assertIn(
            f"Ab dem {FREE_STUDENT_LIMIT + 1}. Schüler und ab der {FREE_INVOICE_MONTHLY_LIMIT + 1}. Rechnung",
            html,
        )
        self.assertIn("Gesperrt wird nichts", html)


class FreeMessagesTest(TestCase):
    def test_translations_say_free_tarif_and_do_not_claim_active_students(self):
        with translation.override("de"):
            students = gettext(
                'Free plan: the limit of 5 students has been reached. Your student was saved — <a href="{}">upgrade to a paid plan</a> for unlimited students.'
            )
            invoices = gettext(
                'Free plan: the limit of 8 invoices per month has been reached. Your invoice was created — <a href="{}">upgrade to a paid plan</a> for unlimited invoices.'
            )
            plan_name = gettext("Free")

        self.assertEqual(plan_name, "Free")
        for text in (students, invoices):
            self.assertTrue(text.startswith("Free-Tarif:"), text)
            self.assertIn("bezahlten Tarif", text)
            self.assertNotIn("Plan", text)
        self.assertNotIn("aktiven", students, "gezählt wird jeder Vertrag, nicht nur aktive")


def _invoice(owner, created_at=None, status="draft", cancels=None):
    invoice = Invoice.objects.create(
        owner=owner,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status=status,
        cancels=cancels,
    )
    if created_at is not None:
        Invoice.objects.filter(pk=invoice.pk).update(created_at=created_at)
    return invoice


class InvoiceMonthCountTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("zaehler", password="pw")
        self.other = User.objects.create_user("zaehler_fremd", password="pw")
        self.now = datetime(2026, 11, 20, 12, 0, tzinfo=dt_timezone.utc)

    def count(self, at=None):
        with mock.patch("django.utils.timezone.now", return_value=at or self.now):
            return invoices_created_this_month(self.owner)

    def test_only_invoices_of_this_calendar_month_count(self):
        _invoice(self.owner, created_at=self.now)
        _invoice(self.owner, created_at=self.now - timedelta(days=25))  # Oktober
        _invoice(self.owner, created_at=self.now + timedelta(days=15))  # Dezember

        self.assertEqual(self.count(), 1)

    def test_the_period_of_the_lessons_does_not_matter_only_the_day_of_creation(self):
        invoice = _invoice(self.owner, created_at=self.now)

        self.assertEqual(invoice.period_start.month, 1, "die Stunden liegen im Januar")
        self.assertEqual(
            self.count(), 1, "gezählt wird der November, in dem die Rechnung angelegt wurde"
        )

    def test_other_accounts_do_not_count(self):
        _invoice(self.other, created_at=self.now)

        self.assertEqual(self.count(), 0)

    def test_a_cancellation_invoice_counts_as_an_invoice(self):
        original = _invoice(self.owner, created_at=self.now - timedelta(days=40), status="sent")
        _invoice(self.owner, created_at=self.now, status="sent", cancels=original)

        self.assertEqual(
            self.count(),
            1,
            "wer eine Rechnung aus dem Vormonat storniert, belegt eine Rechnung im laufenden Monat",
        )

    def test_cancelled_and_paid_invoices_count_too(self):
        for status in ("draft", "sent", "paid", "cancelled"):
            _invoice(self.owner, created_at=self.now, status=status)

        self.assertEqual(self.count(), 4)

    def test_the_month_follows_german_time_at_the_turn_of_the_month(self):
        """30.11. 23:10 UTC ist in Deutschland schon der 1.12. (00:10). Früher las die Zählung den Monat aus UTC (November), die Abfrage
        wertete aber in deutscher Zeit aus (Dezember): In dieser Stunde blieb der Hinweis aus."""
        created = datetime(2026, 11, 30, 23, 10, tzinfo=dt_timezone.utc)
        for _ in range(FREE_INVOICE_MONTHLY_LIMIT):
            _invoice(self.owner, created_at=created)
        shortly_after = datetime(
            2026, 11, 30, 23, 30, tzinfo=dt_timezone.utc
        )  # 1.12. 00:30 deutsche Zeit

        self.assertEqual(self.count(at=shortly_after), FREE_INVOICE_MONTHLY_LIMIT)

    def test_the_same_invoices_belong_to_november_in_the_hour_before(self):
        created = datetime(
            2026, 11, 30, 22, 40, tzinfo=dt_timezone.utc
        )  # 30.11. 23:40 deutsche Zeit
        _invoice(self.owner, created_at=created)
        before_midnight = datetime(2026, 11, 30, 22, 50, tzinfo=dt_timezone.utc)

        self.assertEqual(self.count(at=before_midnight), 1)


class StudentCountTest(TestCase):
    def test_ended_contracts_count_toward_the_student_notice(self):
        from apps.core.models import UserProfile  # noqa: F401 - Profil entsteht beim Anmelden

        user = User.objects.create_user("schueler_zaehler", password="pw")
        self.assertTrue(user.date_joined.year >= 2026)
        for i in range(FREE_STUDENT_LIMIT):
            Contract.objects.create(
                user=user,
                first_name=f"Alt{i}",
                last_name="Beendet",
                hourly_rate=Decimal("20"),
                start_date=date.today(),
                is_active=False,
            )
        self.client.force_login(user)

        response = self.client.post(
            reverse("students:create"),
            {
                "first_name": "Neu",
                "last_name": "Schueler",
                "hourly_rate": "20.00",
                "unit_duration_minutes": "60",
                "start_date": date.today().isoformat(),
            },
        )

        warnings = [m for m in response.wsgi_request._messages if m.level_tag == "warning"]
        self.assertTrue(
            any("Free-Tarif" in str(m) or "Free plan" in str(m) for m in warnings),
            [str(m) for m in warnings],
        )
