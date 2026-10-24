"""Institut: Standard-Stundensatz und Standard-Einheitsdauer, beim Anlegen eines Schülers vorbelegt.

Auftrag von Andreas, 24.10.2026: "Beim Erstellen eines Schülers soll der Stundensatz automatisch gewählt werden,
wenn man ein Institut wählt." und "Auch die Einheitsdauer soll dem Institut entsprechend eingestellt werden."
"""

import datetime as dt
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.contracts.forms import ContractForm, InstituteForm
from apps.contracts.models import Contract, Institute
from apps.core.models import UserProfile

User = get_user_model()

TIERS = [
    {"hours_from": 50, "rate": 18, "label": "18 €/h"},
    {"hours_from": 0, "rate": 14, "label": "14 €/h"},  # absichtlich nicht der erste Eintrag
]


class InstituteFixture(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="inst_tutor", password="pass")
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        self.client.force_login(self.tutor)
        self.explicit = Institute.objects.create(
            user=self.tutor,
            institute_name="Explizit",
            default_hourly_rate=Decimal("27.50"),
            default_unit_duration_minutes=45,
            tiers=TIERS,
        )
        self.tiered = Institute.objects.create(
            user=self.tutor, institute_name="Gestaffelt", tiers=TIERS
        )
        self.bare = Institute.objects.create(user=self.tutor, institute_name="Ohne Angaben")
        stranger = User.objects.create_user(username="inst_stranger", password="pass")
        self.foreign = Institute.objects.create(
            user=stranger,
            institute_name="Fremd",
            default_hourly_rate=Decimal("99.00"),
            default_unit_duration_minutes=99,
        )


class StudentDefaultsTest(InstituteFixture):
    def test_explicit_values_win_over_the_tiers(self):
        self.assertEqual(self.explicit.student_defaults(), {"rate": "27.50", "duration": 45})

    def test_without_an_explicit_rate_the_first_tier_counts_whatever_the_order(self):
        self.assertEqual(self.tiered.student_defaults(), {"rate": "14.00", "duration": None})

    def test_nothing_set_means_nothing_to_fill(self):
        self.assertEqual(self.bare.student_defaults(), {"rate": None, "duration": None})

    def test_a_tier_rate_of_zero_is_not_offered(self):
        self.tiered.tiers = [{"hours_from": 0, "rate": 0, "label": "gratis"}]

        self.assertIsNone(self.tiered.student_defaults()["rate"])

    def test_broken_tiers_do_not_raise(self):
        for broken in (
            [{"rate": 14}],
            [{"hours_from": "x", "rate": 14}],
            [{"hours_from": 0, "rate": "viel"}],
            ["kaputt"],
            "kaputt",
            None,
        ):
            with self.subTest(tiers=broken):
                self.tiered.tiers = broken

                self.assertIsNone(self.tiered.student_defaults()["rate"])

    def test_rates_with_many_decimals_are_rounded_for_the_input(self):
        self.tiered.tiers = [{"hours_from": 0, "rate": 14.5, "label": "x"}]

        self.assertEqual(self.tiered.student_defaults()["rate"], "14.50")


class InstituteFormTest(InstituteFixture):
    def data(self, **extra):
        data = {
            "institute_name": "Neues Institut",
            "tiers": "[]",
            "tutor_no_show_pay_percent": "0",
            "default_hourly_rate": "22.00",
            "default_unit_duration_minutes": "50",
        }
        data.update(extra)
        return data

    def test_the_defaults_are_saved(self):
        form = InstituteForm(data=self.data())

        self.assertTrue(form.is_valid(), form.errors)
        institute = form.save(commit=False)
        self.assertEqual(institute.default_hourly_rate, Decimal("22.00"))
        self.assertEqual(institute.default_unit_duration_minutes, 50)

    def test_both_are_optional(self):
        data = self.data(default_hourly_rate="", default_unit_duration_minutes="")

        form = InstituteForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        institute = form.save(commit=False)
        self.assertIsNone(institute.default_hourly_rate)
        self.assertIsNone(institute.default_unit_duration_minutes)

    def test_limits(self):
        for field, value in [
            ("default_hourly_rate", "0"),
            ("default_hourly_rate", "-5"),
            ("default_unit_duration_minutes", "0"),
            ("default_unit_duration_minutes", "481"),
        ]:
            with self.subTest(field=field, value=value):
                form = InstituteForm(data=self.data(**{field: value}))

                self.assertIn(field, form.errors)

    def test_the_institute_pages_show_the_fields_and_the_defaults(self):
        create = self.client.get(reverse("contracts:institute_create"))
        listing = self.client.get(reverse("contracts:institute_list"))

        self.assertContains(create, 'name="default_hourly_rate"')
        self.assertContains(create, 'name="default_unit_duration_minutes"')
        self.assertContains(create, "Standard für neue Schüler")
        self.assertContains(listing, "27,50 €/h, 45 min")
        self.assertEqual(listing.content.decode().count("Standard für neue Schüler"), 1)

    def test_saving_through_the_page_keeps_the_values(self):
        response = self.client.post(
            reverse("contracts:institute_update", args=[self.bare.pk]),
            self.data(institute_name="Ohne Angaben"),
        )

        self.assertEqual(response.status_code, 302)
        self.bare.refresh_from_db()
        self.assertEqual(self.bare.default_hourly_rate, Decimal("22.00"))
        self.assertEqual(self.bare.default_unit_duration_minutes, 50)


class ContractFormPrefillTest(InstituteFixture):
    def test_the_map_has_only_own_institutes_with_something_to_fill(self):
        form = ContractForm(user=self.tutor)

        self.assertEqual(
            form.institute_defaults,
            {
                str(self.explicit.pk): {"rate": "27.50", "duration": 45},
                str(self.tiered.pk): {"rate": "14.00", "duration": None},
            },
        )

    def test_the_institute_field_is_marked_for_the_script(self):
        form = ContractForm(user=self.tutor)

        attrs = form.fields["institute_fk"].widget.attrs
        self.assertEqual(attrs["data-institute-prefill"], "true")
        self.assertIn("übernommen", str(attrs["data-prefill-message"]))
        self.assertIn("vorbelegt", str(form.fields["hourly_rate"].help_text))
        self.assertIn("vorbelegt", str(form.fields["unit_duration_minutes"].help_text))

    def test_without_any_defaults_nothing_changes(self):
        Institute.objects.exclude(pk=self.bare.pk).filter(user=self.tutor).delete()

        form = ContractForm(user=self.tutor)

        self.assertEqual(form.institute_defaults, {})
        self.assertNotIn("data-institute-prefill", form.fields["institute_fk"].widget.attrs)
        self.assertEqual(str(form.fields["hourly_rate"].help_text), "")

    def test_a_tutor_without_institutes_gets_no_prefill(self):
        other = User.objects.create_user(username="inst_other", password="pass")

        form = ContractForm(user=other)

        self.assertEqual(form.institute_defaults, {})

    def test_editing_a_student_never_prefills(self):
        contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            institute_fk=self.explicit,
            unit_duration_minutes=60,
        )

        form = ContractForm(instance=contract, user=self.tutor)

        self.assertEqual(form.institute_defaults, {})
        self.assertNotIn("data-institute-prefill", form.fields["institute_fk"].widget.attrs)

    def test_a_form_that_was_submitted_keeps_what_the_tutor_typed(self):
        form = ContractForm(data={"first_name": "x"}, user=self.tutor)

        self.assertEqual(form.institute_defaults, {})
        self.assertNotIn("data-institute-prefill", form.fields["institute_fk"].widget.attrs)


class PagesTest(InstituteFixture):
    def test_both_create_pages_ship_the_defaults_and_the_script(self):
        for name in ("contracts:create", "students:create"):
            with self.subTest(seite=name):
                page = self.client.get(reverse(name))

                self.assertContains(page, 'id="institute-defaults"')
                self.assertContains(page, '"rate": "27.50"')
                self.assertContains(page, '"duration": 45')
                self.assertContains(page, "institute-defaults.js")
                self.assertContains(page, 'data-institute-prefill="true"')
                self.assertNotContains(page, '"rate": "99.00"')  # Institut eines anderen Tutors

    def test_the_edit_pages_do_not(self):
        contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            unit_duration_minutes=60,
        )
        for name in ("contracts:update", "students:update"):
            with self.subTest(seite=name):
                page = self.client.get(reverse(name, args=[contract.pk]))

                self.assertNotContains(page, 'id="institute-defaults"')
                self.assertNotContains(page, "institute-defaults.js")

    def test_the_script_exists_and_has_the_guards(self):
        script = (
            Path(__file__).resolve().parents[1] / "core" / "static" / "js" / "institute-defaults.js"
        )
        text = script.read_text(encoding="utf-8")

        self.assertIn("data-institute-prefill", text)
        self.assertIn("dataset.touched", text)  # eigene Eingaben bleiben
        self.assertIn("role", text)  # Hinweis für Screenreader

    def test_the_server_never_overrides_what_the_tutor_submits(self):
        response = self.client.post(
            reverse("contracts:create"),
            {
                "first_name": "Neu",
                "last_name": "Schüler",
                "institute_fk": self.explicit.pk,
                "hourly_rate": "31.00",
                "unit_duration_minutes": "90",
                "start_date": "2026-10-01",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        contract = Contract.objects.get(first_name="Neu")
        self.assertEqual(contract.hourly_rate, Decimal("31.00"))
        self.assertEqual(contract.unit_duration_minutes, 90)  # nicht 45 aus dem Institut

    def test_existing_contracts_and_lessons_keep_their_values(self):
        contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("20.00"),
            start_date=dt.date(2025, 1, 1),
            institute_fk=self.explicit,
            unit_duration_minutes=60,
        )

        self.explicit.default_hourly_rate = Decimal("50.00")
        self.explicit.default_unit_duration_minutes = 30
        self.explicit.save()
        contract.refresh_from_db()

        self.assertEqual(contract.hourly_rate, Decimal("20.00"))
        self.assertEqual(contract.unit_duration_minutes, 60)

    def test_the_faq_explains_it(self):
        page = self.client.get(reverse("core:faq"))

        self.assertContains(page, "Standard für neue Schüler")
        self.assertContains(page, "Bei bestehenden Schülern ändert sich nichts")
