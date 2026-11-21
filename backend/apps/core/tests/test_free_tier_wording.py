"""Free-Tarif: Der Wortlaut der Oberfläche entspricht dem tatsächlichen Verhalten.

Befund vom 20.11.2026 (Prüfung der Aussage „wird durchgesetzt“): Die Grenzen sind **weich**. Beim Anlegen des 6. Vertrags und der 9. Rechnung eines Kalendermonats
zeigt Preceptly einen Hinweis auf die bezahlten Tarife; gespeichert wird trotzdem, es wird nichts gesperrt (PRD, `free_limits.py`, `test_free_plan_limits.py`). Gezählt wird:
- „Schüler“: **Verträge**, nicht verschiedene Personen. Es gibt keine eigene Schüler-Tabelle; Vor- und Nachname stehen am Vertrag und sind nicht eindeutig. Dieselbe Person mit zwei
  Verträgen zählt zweimal. Beendete (`end_date`) und inaktive (`is_active=False`) Verträge zählen mit, bis sie gelöscht werden (Stand 21.11.2026: Text hieß bis dahin „Schüler“),
- Rechnungen: jede im laufenden Kalendermonat (deutsche Zeit) angelegte Rechnung, unabhängig vom Zeitraum der Stunden; Stornorechnungen sind eigene Rechnungen und zählen mit.
Die Hinweise gelten nur für Free-Konten ab dem 02.07.2026.

Diese Tests halten Startseite, FAQ und Meldungen an diese Regeln und an die Konstanten in `feature_flags.py`. Die Zähllogik selbst bleibt unverändert.
"""

import inspect
import re
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

        self.assertIn(f"Gedacht für bis zu {FREE_STUDENT_LIMIT} Schülerverträge", de)
        self.assertIn(f"Gedacht für bis zu {FREE_INVOICE_MONTHLY_LIMIT} Rechnungen im Monat", de)
        self.assertIn(f"Intended for up to {FREE_STUDENT_LIMIT} student contracts", en)
        self.assertIn(f"Intended for up to {FREE_INVOICE_MONTHLY_LIMIT} invoices per month", en)
        self.assertNotIn(
            "Bis zu 5 Schüler", de, "„Bis zu“ klingt nach harter Grenze; es ist ein Hinweis"
        )

    def test_the_student_limit_is_never_worded_as_a_number_of_people(self):
        # Gezählt werden Verträge. „bis zu 5 Schüler“ ohne „-verträge“ würde als Zahl verschiedener Personen gelesen.
        pages = {
            "landing de": get_in(self.client, "core:landing", "de").content.decode(),
            "landing en": get_in(self.client, "core:landing", "en").content.decode(),
            "faq": self.client.get(reverse("core:faq")).content.decode(),
        }
        for name, html in pages.items():
            with self.subTest(seite=name):
                self.assertIsNone(
                    re.search(
                        rf"(?:bis zu|up to) {FREE_STUDENT_LIMIT} (?:Schüler(?!verträge)|students)",
                        html,
                    ),
                    "die Zahl gilt Verträgen, nicht Personen",
                )

    def test_the_note_names_the_trigger_and_says_nothing_is_blocked(self):
        de = get_in(self.client, "core:landing", "de").content.decode()
        en = get_in(self.client, "core:landing", "en").content.decode()

        # Der Hinweis kommt beim Anlegen des (Limit + 1). Vertrags und der (Limit + 1). Rechnung, danach bei jedem weiteren
        self.assertIn(
            f"den {FREE_STUDENT_LIMIT + 1}. Schülervertrag anlegst und wenn du in einem Kalendermonat die {FREE_INVOICE_MONTHLY_LIMIT + 1}. Rechnung anlegst",
            de,
        )
        self.assertIn("und danach bei jedem weiteren", de)
        self.assertIn("Gesperrt wird nichts: Alles wird gespeichert", de)
        self.assertIn("du kannst Preceptly wie gewohnt weiter nutzen", de)
        self.assertIn("auch Stornorechnungen", de)
        self.assertIn("Nothing is blocked: everything is saved", en)
        self.assertIn("you can keep using Preceptly as usual", en)
        self.assertIn(
            f"the {FREE_STUDENT_LIMIT + 1}th student contract and when you create the {FREE_INVOICE_MONTHLY_LIMIT + 1}th invoice",
            en,
        )

    def test_the_note_says_that_contracts_are_counted_not_people(self):
        de = get_in(self.client, "core:landing", "de").content.decode()
        en = get_in(self.client, "core:landing", "en").content.decode()

        self.assertIn("Gezählt werden Verträge, nicht verschiedene Personen", de)
        self.assertIn("Hat dieselbe Person zwei Verträge, zählen beide", de)
        self.assertIn(
            "Beendete und inaktive Verträge zählen mit, solange sie nicht gelöscht sind", de
        )
        self.assertIn("Contracts are counted, not different people", en)
        self.assertIn("if the same person has two contracts, both count", en)
        self.assertIn("Ended and inactive contracts count as long as they are not deleted", en)

    def test_the_faq_uses_free_and_states_the_same_rules(self):
        html = self.client.get(reverse("core:faq")).content.decode()

        self.assertIn("Free (kostenlos):", html)
        self.assertNotIn("Basic (kostenlos)", html)
        self.assertIn(
            f"Beim Anlegen des {FREE_STUDENT_LIMIT + 1}. Vertrags und der {FREE_INVOICE_MONTHLY_LIMIT + 1}. Rechnung eines Kalendermonats",
            html,
        )
        self.assertIn("Gesperrt wird nichts", html)
        self.assertIn("die Nutzung geht normal weiter", html)
        self.assertIn("Gezählt werden Verträge, nicht verschiedene Personen", html)
        self.assertIn(
            "beendete und inaktive Verträge zählen mit, solange sie nicht gelöscht sind", html
        )


STUDENT_NOTICE = (
    "Free plan: you now have more than 5 student contracts. The Free plan is intended for up to 5; every contract counts, including ended ones and "
    'several for the same person. Your entry was saved and nothing is blocked. <a href="{}">See the paid plans</a>'
)
INVOICE_NOTICE = (
    "Free plan: you have now created more than 8 invoices this calendar month. The Free plan is intended for up to 8 per month; every invoice created "
    'in the month counts, including cancellation invoices. Your invoice was created and nothing is blocked. <a href="{}">See the paid plans</a>'
)


class FreeMessagesTest(TestCase):
    def test_translations_say_free_tarif_and_do_not_promise_a_cap(self):
        with translation.override("de"):
            students = gettext(STUDENT_NOTICE)
            invoices = gettext(INVOICE_NOTICE)
            plan_name = gettext("Free")

        self.assertEqual(plan_name, "Free")
        for text in (students, invoices):
            self.assertTrue(text.startswith("Free-Tarif:"), text)
            self.assertIn("bezahlten Tarifen", text)
            self.assertIn("gesperrt ist nichts", text)
            self.assertNotIn("Plan", text)
            self.assertNotIn(
                "unbegrenzt",
                text,
                "Free-Konten sind nicht begrenzt; ein Upgrade verspricht hier nichts Neues",
            )
            self.assertNotIn("Grenze", text, "es ist ein Hinweis, keine Grenze")
        self.assertNotIn("aktiven", students, "gezählt wird jeder Vertrag, nicht nur aktive")
        self.assertIn("Schülerverträge", students)
        self.assertIn("mehrere derselben Person", students)
        self.assertIn("Stornorechnungen", invoices)

    def test_the_invoice_notice_in_the_view_is_the_one_translated_here(self):
        from apps.billing import views as billing_views

        source = inspect.getsource(billing_views)
        self.assertIn("you have now created more than 8 invoices this calendar month.", source)
        self.assertIn("The Free plan is intended for up to 8 per month;", source)
        self.assertIn("Your invoice was created and nothing is blocked.", source)

    def test_the_numbers_in_the_notices_are_the_limits(self):
        self.assertIn(f"more than {FREE_STUDENT_LIMIT} student contracts", STUDENT_NOTICE)
        self.assertIn(f"up to {FREE_STUDENT_LIMIT};", STUDENT_NOTICE)
        self.assertIn(f"more than {FREE_INVOICE_MONTHLY_LIMIT} invoices", INVOICE_NOTICE)
        self.assertIn(f"up to {FREE_INVOICE_MONTHLY_LIMIT} per month", INVOICE_NOTICE)


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


class ContractCountTest(TestCase):
    """Gezählt werden Verträge, nicht verschiedene Personen (es gibt keine eigene Schüler-Tabelle).

    Alle Fälle laufen über den echten Anlegeweg („Schüler anlegen“). Der Hinweis erscheint, wenn schon `FREE_STUDENT_LIMIT` Verträge bestehen.
    """

    def setUp(self):
        self.user = User.objects.create_user("vertrags_zaehler", password="pw")
        self.client.force_login(self.user)

    def contract(self, first, last, **extra):
        return Contract.objects.create(
            user=self.user,
            first_name=first,
            last_name=last,
            hourly_rate=Decimal("20"),
            start_date=date.today(),
            **extra,
        )

    def create_student(self, lang="de"):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
        # Meldungen früherer Anlegevorgänge warten in der Sitzung, bis eine Seite sie anzeigt; hier wird nur die Meldung dieses Vorgangs gelesen
        self.client.get(reverse("students:list"))
        response = self.client.post(
            reverse("students:create"),
            {
                "first_name": "Neu",
                "last_name": "Person",
                "hourly_rate": "20.00",
                "unit_duration_minutes": "60",
                "start_date": date.today().isoformat(),
            },
        )
        warnings = [str(m) for m in response.wsgi_request._messages if m.level_tag == "warning"]
        return response, warnings

    def test_the_notice_comes_with_the_sixth_contract_not_the_fifth(self):
        for i in range(FREE_STUDENT_LIMIT - 1):
            self.contract(f"Person{i}", "Test")

        _, warnings = self.create_student()  # 5. Vertrag
        self.assertEqual(warnings, [])

        _, warnings = self.create_student()  # 6. Vertrag
        self.assertEqual(len(warnings), 1, warnings)
        self.assertEqual(Contract.objects.filter(user=self.user).count(), FREE_STUDENT_LIMIT + 1)

    def test_the_same_person_with_two_contracts_counts_twice(self):
        # fünf Verträge, aber nur vier verschiedene Personen: Zählte man Personen, bliebe der Hinweis aus
        self.contract("Anna", "Alt")
        self.contract("Anna", "Alt")
        self.contract("Ben", "Bruder")
        self.contract("Clara", "Clau")
        self.contract("Dora", "Dorn")
        distinct = {(c.first_name, c.last_name) for c in Contract.objects.filter(user=self.user)}
        self.assertEqual(len(distinct), FREE_STUDENT_LIMIT - 1)
        self.assertEqual(Contract.objects.filter(user=self.user).count(), FREE_STUDENT_LIMIT)

        response, warnings = self.create_student()

        self.assertEqual(len(warnings), 1, warnings)
        self.assertEqual(response.status_code, 302, "gespeichert wird trotzdem")

    def test_ended_and_inactive_contracts_count(self):
        yesterday = date.today() - timedelta(days=1)
        for i in range(3):
            self.contract(f"Beendet{i}", "Test", end_date=yesterday)
        for i in range(FREE_STUDENT_LIMIT - 3):
            self.contract(f"Inaktiv{i}", "Test", is_active=False)

        _, warnings = self.create_student()

        self.assertEqual(len(warnings), 1, warnings)

    def test_deleting_a_contract_takes_it_out_of_the_count(self):
        contracts = [self.contract(f"Person{i}", "Test") for i in range(FREE_STUDENT_LIMIT)]
        self.client.post(reverse("students:delete", args=[contracts[0].pk]))
        self.assertEqual(Contract.objects.filter(user=self.user).count(), FREE_STUDENT_LIMIT - 1)

        _, warnings = self.create_student()  # wieder der 5. Vertrag
        self.assertEqual(warnings, [])

        _, warnings = self.create_student()  # jetzt der 6.
        self.assertEqual(len(warnings), 1, warnings)

    def test_every_further_contract_shows_the_notice_and_nothing_is_blocked(self):
        for i in range(FREE_STUDENT_LIMIT):
            self.contract(f"Person{i}", "Test")

        for _ in range(2):
            response, warnings = self.create_student()
            self.assertEqual(response.status_code, 302)
            self.assertEqual(len(warnings), 1, warnings)

        self.assertEqual(Contract.objects.filter(user=self.user).count(), FREE_STUDENT_LIMIT + 2)

    def test_the_notice_says_contracts_and_that_nothing_is_blocked_in_both_languages(self):
        for i in range(FREE_STUDENT_LIMIT):
            self.contract(f"Person{i}", "Test")

        _, de = self.create_student("de")
        _, en = self.create_student("en")

        self.assertIn(f"mehr als {FREE_STUDENT_LIMIT} Schülerverträge", de[0])
        self.assertIn("gesperrt ist nichts", de[0])
        self.assertIn(f"more than {FREE_STUDENT_LIMIT} student contracts", en[0])
        self.assertIn("nothing is blocked", en[0])
