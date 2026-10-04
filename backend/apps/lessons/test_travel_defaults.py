"""Standard-Fahrzeiten je Schüler: am Vertrag, bei neuen Stunden vorbelegt, je Stunde änderbar.

Auftrag von Andreas, 04.10.2026."""

import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.forms import SessionForm
from apps.lessons.models import Session
from apps.lessons.recurring_forms import RecurringLessonForm
from apps.lessons.recurring_models import RecurringSession
from apps.portal.models import ParentStudentLink, PortalUser

User = get_user_model()


def _contract(tutor, first, before=0, after=0):
    return Contract.objects.create(
        user=tutor,
        first_name=first,
        last_name="Test",
        hourly_rate=Decimal("20.00"),
        unit_duration_minutes=60,
        start_date=dt.date(2025, 1, 1),
        is_active=True,
        default_travel_time_before_minutes=before,
        default_travel_time_after_minutes=after,
    )


class TravelDefaultsFixture(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(username="travel_tutor", password="pass")
        UserProfile.objects.update_or_create(user=self.tutor, defaults={"subscription_tier": "pro"})
        self.far = _contract(self.tutor, "Weit", 25, 20)
        self.near = _contract(self.tutor, "Nah")
        stranger = User.objects.create_user(username="travel_stranger", password="pass")
        self.foreign = _contract(stranger, "Fremd", 99, 99)
        self.client.force_login(self.tutor)
        self.day = dt.date.today() + dt.timedelta(days=3)


class ContractTravelDefaultsTest(TravelDefaultsFixture):
    def _data(self, **extra):
        data = {
            "first_name": "Neu",
            "last_name": "Schüler",
            "hourly_rate": "20.00",
            "unit_duration_minutes": "60",
            "default_travel_time_before_minutes": "15",
            "default_travel_time_after_minutes": "10",
            "start_date": "2026-10-01",
            "is_active": "on",
        }
        data.update(extra)
        return data

    def test_contract_form_saves_the_defaults(self):
        form = ContractForm(data=self._data(), user=self.tutor)

        self.assertTrue(form.is_valid(), form.errors)
        form.instance.user = self.tutor
        contract = form.save()
        self.assertEqual(
            (
                contract.default_travel_time_before_minutes,
                contract.default_travel_time_after_minutes,
            ),
            (15, 10),
        )

    def test_defaults_are_optional_and_limited(self):
        without = self._data()
        del without["default_travel_time_before_minutes"]
        without["default_travel_time_after_minutes"] = ""
        form = ContractForm(data=without, user=self.tutor)

        self.assertTrue(form.is_valid(), form.errors)  # leer heißt 0
        self.assertEqual(form.cleaned_data["default_travel_time_before_minutes"], 0)
        self.assertEqual(form.cleaned_data["default_travel_time_after_minutes"], 0)

        too_long = self._data(default_travel_time_before_minutes="481")
        self.assertIn(
            "default_travel_time_before_minutes",
            ContractForm(data=too_long, user=self.tutor).errors,
        )

    def test_contract_page_shows_the_defaults_only_when_set(self):
        far = self.client.get(reverse("contracts:detail", args=[self.far.pk]))
        near = self.client.get(reverse("contracts:detail", args=[self.near.pk]))

        self.assertContains(far, "25 Min. vorher, 20 Min. nachher")
        self.assertNotContains(near, "Standard-Fahrzeit")


class LessonFormTravelDefaultsTest(TravelDefaultsFixture):
    def test_new_lesson_is_prefilled_from_the_chosen_student(self):
        form = SessionForm(user=self.tutor, initial={"contract": self.far.pk})

        self.assertEqual(form.initial["travel_time_before_minutes"], 25)
        self.assertEqual(form.initial["travel_time_after_minutes"], 20)
        self.assertEqual(form.fields["contract"].widget.attrs["data-travel-prefill"], "true")
        self.assertIn("vorbelegt", str(form.fields["travel_time_before_minutes"].help_text))

    def test_defaults_of_all_own_students_ship_with_the_form_but_not_foreign_ones(self):
        form = SessionForm(user=self.tutor)

        self.assertEqual(
            form.contract_travel_defaults,
            {
                str(self.far.pk): {"before": 25, "after": 20},
                str(self.near.pk): {"before": 0, "after": 0},
            },
        )

    def test_without_a_chosen_student_nothing_is_prefilled(self):
        form = SessionForm(user=self.tutor)

        self.assertNotIn("travel_time_before_minutes", form.initial)
        self.assertEqual(form.fields["travel_time_before_minutes"].initial, 0)
        self.assertEqual(form.fields["travel_time_after_minutes"].initial, 0)

    def test_editing_and_resubmitting_do_not_prefill(self):
        lesson = Session.objects.create(
            contract=self.far,
            date=self.day,
            start_time=dt.time(16, 0),
            duration_minutes=60,
            travel_time_before_minutes=5,
            travel_time_after_minutes=7,
        )
        editing = SessionForm(user=self.tutor, instance=lesson)
        resubmitted = SessionForm(
            user=self.tutor, data={"contract": self.far.pk, "travel_time_before_minutes": "3"}
        )

        self.assertNotIn("data-travel-prefill", editing.fields["contract"].widget.attrs)
        self.assertEqual(editing.initial["travel_time_before_minutes"], 5)
        self.assertNotIn("data-travel-prefill", resubmitted.fields["contract"].widget.attrs)

    def test_series_form_ships_the_defaults_too(self):
        form = RecurringLessonForm(user=self.tutor, initial={"contract": self.far.pk})

        self.assertEqual(
            form.contract_travel_defaults[str(self.far.pk)], {"before": 25, "after": 20}
        )
        self.assertEqual(form.initial["travel_time_before_minutes"], 25)

    def test_pages_ship_the_json_and_the_script(self):
        for name in ("lessons:create", "lessons:recurring_create"):
            with self.subTest(seite=name):
                page = self.client.get(reverse(name))

                self.assertContains(page, 'id="contract-travel-defaults"')
                self.assertContains(page, '"before": 25')
                self.assertContains(page, "travel-defaults.js")
                self.assertNotContains(page, str(self.foreign.pk) + '": {"before": 99')

    def _post(self, **travel):
        data = {
            "contract": self.far.pk,
            "date": self.day.isoformat(),
            "start_time": "16:00",
            "duration_minutes": 60,
            "travel_time_before_minutes": travel.get("before", 25),
            "travel_time_after_minutes": travel.get("after", 20),
            "notes": "",
        }
        return self.client.post(reverse("lessons:create"), data)

    def test_the_tutor_can_change_the_travel_times_for_a_single_lesson(self):
        self._post(before=5, after=0)

        lesson = Session.objects.get(contract=self.far)
        self.assertEqual(
            (lesson.travel_time_before_minutes, lesson.travel_time_after_minutes), (5, 0)
        )
        self.far.refresh_from_db()
        self.assertEqual(self.far.default_travel_time_before_minutes, 25)  # Standard bleibt

    def test_prefilled_values_are_saved_as_they_are(self):
        self._post()

        lesson = Session.objects.get(contract=self.far)
        self.assertEqual(
            (lesson.travel_time_before_minutes, lesson.travel_time_after_minutes), (25, 20)
        )

    def test_changing_the_contract_leaves_existing_lessons_alone(self):
        self._post()
        self.far.default_travel_time_before_minutes = 0
        self.far.default_travel_time_after_minutes = 0
        self.far.save()

        lesson = Session.objects.get(contract=self.far)
        self.assertEqual(
            (lesson.travel_time_before_minutes, lesson.travel_time_after_minutes), (25, 20)
        )


class PortalBookingsUseTheDefaultsTest(TravelDefaultsFixture):
    def setUp(self):
        super().setUp()
        self.client.logout()
        account = PortalUser.objects.create(
            user=User.objects.create_user(username="travel_portal", password="pass"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(parent=account, contract=self.far, is_active=True)
        session = self.client.session
        session["portal_user_id"] = account.pk
        session.save()

    def test_single_booking_takes_the_standard_travel_times(self):
        self.client.post(
            reverse("portal:book", kwargs={"student_pk": self.far.pk}),
            {"date": self.day.isoformat(), "start_time": "16:00"},
        )

        lesson = Session.objects.get(contract=self.far)
        self.assertEqual(
            (lesson.travel_time_before_minutes, lesson.travel_time_after_minutes), (25, 20)
        )

    def test_series_and_its_lessons_take_the_standard_travel_times(self):
        monday = self.day + dt.timedelta(days=(7 - self.day.weekday()) % 7 or 7)
        self.client.post(
            reverse("portal:recurring_create", kwargs={"student_pk": self.far.pk}),
            {
                "start_time": "16:00",
                "start_date": monday.isoformat(),
                "end_date": (monday + dt.timedelta(days=14)).isoformat(),
                "monday": "on",
            },
        )

        series = RecurringSession.objects.get(contract=self.far)
        self.assertEqual(
            (series.travel_time_before_minutes, series.travel_time_after_minutes), (25, 20)
        )
        lessons = Session.objects.filter(recurring_session=series)
        self.assertEqual(lessons.count(), 3)
        for lesson in lessons:
            self.assertEqual(
                (lesson.travel_time_before_minutes, lesson.travel_time_after_minutes), (25, 20)
            )
