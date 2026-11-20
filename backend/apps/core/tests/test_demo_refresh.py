"""Demo-Daten verschieben sich mit der Zeit.

Meldung von Andreas, 20.11.2026: "Die Demo-Daten sollten sich mit der Zeit verschieben." Ausgangslage in der Produktion: Die Demo-Konten
waren zuletzt am 23.06.2026 erzeugt worden, `demo_premium` hatte keine einzige Stunde ab heute. Der Seed enthielt feste Daten aus 2025, und
das "stündliche Zurücksetzen per Cron" aus dem Kommentar von `demo_guard` gab es nicht.

Jetzt rechnet der Seed alles vom heutigen Datum aus, und `DemoFreshnessMiddleware` erzeugt die Daten einmal je Kalendertag neu.
"""

from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.blocked_times.models import BlockedTime
from apps.calendar_sync.models import TutorCalendarFeed
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.core.demo_refresh import RETRY_SECONDS, _lock_key, refresh_demo_data_if_due
from apps.core.models import Expense, UserProfile
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson


def seed_on(day, *args):
    """Seed so ausführen, als wäre es 10:00 Uhr deutscher Zeit am Tag `day`."""
    fake_now = datetime(day.year, day.month, day.day, 9, 0, tzinfo=dt_timezone.utc)
    with mock.patch("django.utils.timezone.now", return_value=fake_now):
        call_command("seed_demo_data", *args, stdout=StringIO())


def demo_contracts():
    return Contract.objects.filter(user__username__in=["demo_premium", "demo_user"])


def demo_lessons():
    return Lesson.objects.filter(contract__in=demo_contracts())


class SeedIsRelativeToTodayTest(TestCase):
    # Gewöhnlicher Tag, Jahreswechsel, Schaltjahr, Monatsende, Monatsanfang
    DAYS = (
        date(2026, 11, 20),
        date(2026, 12, 31),
        date(2027, 1, 1),
        date(2028, 2, 29),
        date(2027, 3, 31),
        date(2030, 6, 1),
    )

    def test_nothing_is_dated_far_away_from_the_day_it_was_seeded(self):
        for day in self.DAYS:
            with self.subTest(day=day):
                seed_on(day, "--refresh")

                lessons = list(demo_lessons().values_list("date", flat=True))
                self.assertTrue(lessons)
                self.assertGreaterEqual(min(lessons), day - timedelta(days=10))
                self.assertLessEqual(
                    max(lessons), day + timedelta(days=75), "die Serien sind etwa acht Wochen lang"
                )
                starts = list(demo_contracts().values_list("start_date", flat=True))
                self.assertTrue(all(day - timedelta(days=110) <= s <= day for s in starts), starts)
                blocked = [
                    timezone_date(b)
                    for b in BlockedTime.objects.values_list("start_datetime", flat=True)
                ]
                self.assertTrue(
                    all(day - timedelta(days=1) <= b <= day + timedelta(days=12) for b in blocked),
                    blocked,
                )

    def test_there_is_always_something_coming_up(self):
        for day in self.DAYS:
            with self.subTest(day=day):
                seed_on(day, "--refresh")

                for username in ("demo_premium", "demo_user"):
                    upcoming = Lesson.objects.filter(
                        contract__user__username=username,
                        date__gt=day,
                        date__lte=day + timedelta(days=7),
                    ).count()
                    self.assertGreater(
                        upcoming, 0, f"{username} hat in der nächsten Woche keine Stunde"
                    )

    def test_the_quota_conflict_sits_in_the_next_month_and_is_still_a_conflict(self):
        for day in self.DAYS:
            with self.subTest(day=day):
                seed_on(day, "--refresh")

                first_of_next_month = date(day.year + day.month // 12, day.month % 12 + 1, 1)
                contract = Contract.objects.get(first_name="Max", last_name="Mustermann")
                plan = ContractMonthlyPlan.objects.get(
                    contract=contract,
                    year=first_of_next_month.year,
                    month=first_of_next_month.month,
                )
                in_next_month = Lesson.objects.filter(
                    contract=contract, date__year=plan.year, date__month=plan.month
                ).count()
                self.assertEqual(plan.planned_units, 3)
                # Vier Stunden bei drei geplanten: Die vierte ist der Quotenkonflikt. Am Monatsende kommen die Stunden von morgen
                # und übermorgen dazu (sie liegen schon im nächsten Monat), dann sind es mehr, aber nie weniger.
                self.assertGreaterEqual(in_next_month, 4)
                self.assertGreater(in_next_month, plan.planned_units)
                self.assertTrue(
                    ContractMonthlyPlan.objects.filter(
                        contract=contract, year=day.year, month=day.month
                    ).exists(),
                    "auch der laufende Monat hat einen Plan",
                )

    def test_the_demo_shifts_when_the_seed_runs_again_later(self):
        seed_on(date(2026, 11, 20), "--refresh")
        first = sorted(
            demo_lessons()
            .filter(contract__user__username="demo_premium")
            .values_list("date", flat=True)
        )

        seed_on(date(2027, 1, 15), "--refresh")
        second = sorted(
            demo_lessons()
            .filter(contract__user__username="demo_premium")
            .values_list("date", flat=True)
        )

        self.assertGreaterEqual(min(second), date(2027, 1, 15) - timedelta(days=10))
        self.assertLess(
            max(first),
            date(2027, 1, 15),
            "die Stunden vom November liegen nach dem Auffrischen nicht mehr in der Demo",
        )


def timezone_date(value):
    from django.utils import timezone

    return timezone.localtime(value).date()


class RefreshKeepsTheAccountsTest(TestCase):
    def test_accounts_and_profiles_stay_and_the_data_is_replaced(self):
        seed_on(date(2026, 11, 20), "--refresh")
        premium = User.objects.get(username="demo_premium")
        standard = User.objects.get(username="demo_user")
        profile_ids = set(
            UserProfile.objects.filter(user__in=[premium, standard]).values_list("pk", flat=True)
        )
        old_contracts = set(demo_contracts().values_list("pk", flat=True))

        seed_on(date(2026, 11, 21), "--refresh")

        self.assertEqual(
            User.objects.get(username="demo_premium").pk,
            premium.pk,
            "ein laufender Login darf nicht abbrechen",
        )
        self.assertEqual(User.objects.get(username="demo_user").pk, standard.pk)
        self.assertEqual(
            set(
                UserProfile.objects.filter(user__in=[premium, standard]).values_list(
                    "pk", flat=True
                )
            ),
            profile_ids,
        )
        self.assertFalse(
            old_contracts & set(demo_contracts().values_list("pk", flat=True)),
            "die Verträge sind neu erzeugt",
        )
        self.assertEqual(UserProfile.objects.get(user=premium).subscription_tier, "business")
        self.assertEqual(UserProfile.objects.get(user=standard).subscription_tier, "free")

    def test_the_password_of_the_public_demo_is_reset(self):
        seed_on(date(2026, 11, 20), "--refresh")
        user = User.objects.get(username="demo_user")
        user.set_password("von-einem-besucher-geaendert")
        user.save()

        seed_on(date(2026, 11, 21), "--refresh")

        self.assertTrue(User.objects.get(username="demo_user").check_password("demo123"))

    def test_what_visitors_left_behind_is_removed(self):
        seed_on(date(2026, 11, 20), "--refresh")
        premium = User.objects.get(username="demo_premium")
        Expense.objects.create(
            user=premium,
            date=date(2026, 11, 1),
            amount=Decimal("9.99"),
            category="office",
            description="Besucher",
            business_use_percent=100,
        )
        TutorCalendarFeed.objects.create(user=premium)
        Contract.objects.create(
            user=premium,
            first_name="Besucher",
            last_name="Eintrag",
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=date(2026, 11, 1),
        )

        seed_on(date(2026, 11, 21), "--refresh")

        self.assertFalse(Expense.objects.filter(user=premium).exists())
        self.assertFalse(
            TutorCalendarFeed.objects.filter(user=premium).exists(),
            "die geheime Abo-Adresse eines Besuchers bleibt nicht liegen",
        )
        self.assertFalse(Contract.objects.filter(first_name="Besucher").exists())

    def test_every_kind_of_visitor_leftover_is_removed(self):
        from apps.calendar_sync.models import CalendarConnection, IcsCalendarSource
        from apps.core.models import PushSubscription
        from apps.portal.models import PortalUser

        seed_on(date(2026, 11, 20), "--refresh")
        premium = User.objects.get(username="demo_premium")
        IcsCalendarSource.objects.create(
            user=premium,
            name="Privat",
            encrypted_url=b"geheim",
            url_hash="a" * 64,
            host="calendar.google.com",
        )
        CalendarConnection.objects.create(
            user=premium, provider=CalendarConnection.PROVIDER_CHOICES[0][0]
        )
        PushSubscription.objects.create(
            user=premium, endpoint="https://push.example.com/abc", p256dh="k", auth="a"
        )
        portal_login = User.objects.create_user(
            "portal_besucher", password="pw", email="besucher@example.com"
        )
        PortalUser.objects.create(user=portal_login, role="parent", tutor=premium)

        seed_on(date(2026, 11, 21), "--refresh")

        self.assertFalse(
            IcsCalendarSource.objects.filter(user=premium).exists(),
            "eine Google-Adresse darf nicht in der Demo liegen bleiben",
        )
        self.assertFalse(CalendarConnection.objects.filter(user=premium).exists())
        self.assertFalse(PushSubscription.objects.filter(user=premium).exists())
        self.assertFalse(PortalUser.objects.filter(tutor=premium).exists())
        # Der Login selbst bleibt: Die Einladung kann ein echtes, schon bestehendes Konto getroffen haben.
        self.assertTrue(User.objects.filter(username="portal_besucher").exists())

    def test_the_plan_of_the_demo_accounts_is_reset(self):
        seed_on(date(2026, 11, 20), "--refresh")
        UserProfile.objects.filter(user__username="demo_premium").update(subscription_tier="free")
        UserProfile.objects.filter(user__username="demo_user").update(subscription_tier="business")

        seed_on(date(2026, 11, 21), "--refresh")

        self.assertEqual(
            UserProfile.objects.get(user__username="demo_premium").subscription_tier, "business"
        )
        self.assertEqual(
            UserProfile.objects.get(user__username="demo_user").subscription_tier, "free"
        )

    def test_other_accounts_are_never_touched(self):
        seed_on(date(2026, 11, 20), "--refresh")
        other = User.objects.create_user("echter_tutor", password="pw", email="echt@example.com")
        UserProfile.objects.create(user=other, subscription_tier="pro")
        Contract.objects.create(
            user=other,
            first_name="Echt",
            last_name="Schueler",
            hourly_rate=Decimal("30.00"),
            unit_duration_minutes=60,
            start_date=date(2026, 9, 1),
        )
        Expense.objects.create(
            user=other,
            date=date(2026, 11, 1),
            amount=Decimal("5.00"),
            category="office",
            description="echt",
            business_use_percent=100,
        )

        seed_on(date(2026, 11, 21), "--refresh")

        self.assertTrue(Contract.objects.filter(user=other, first_name="Echt").exists())
        self.assertTrue(Expense.objects.filter(user=other).exists())
        self.assertTrue(User.objects.filter(username="echter_tutor").exists())


class RefreshOncePerDayTest(TestCase):
    def setUp(self):
        cache.clear()
        seed_on(date(2025, 11, 1), "--refresh")  # der Stand, den die Produktion hatte: lange her
        self.demo = User.objects.get(username="demo_premium")

    def refresh(self, user, day):
        with mock.patch("apps.core.demo_refresh.call_command") as seed:
            result = refresh_demo_data_if_due(user, today=day)
        return result, seed

    def test_it_refreshes_once_per_day_and_again_on_the_next_day(self):
        first, seed = self.refresh(self.demo, date(2026, 11, 20))
        again, seed_again = self.refresh(self.demo, date(2026, 11, 20))
        tomorrow, seed_tomorrow = self.refresh(self.demo, date(2026, 11, 21))

        self.assertTrue(first)
        seed.assert_called_once_with("seed_demo_data", "--refresh", stdout=mock.ANY)
        self.assertFalse(again)
        seed_again.assert_not_called()
        self.assertTrue(tomorrow)
        seed_tomorrow.assert_called_once()

    def test_only_demo_accounts_trigger_it(self):
        normal = User.objects.create_user("normal", password="pw")

        result, seed = self.refresh(normal, date(2026, 11, 20))

        self.assertFalse(result)
        seed.assert_not_called()
        self.assertFalse(refresh_demo_data_if_due(None, today=date(2026, 11, 20)))

    def test_a_failure_changes_nothing_raises_nothing_and_allows_a_retry(self):
        contracts_before = set(demo_contracts().values_list("pk", flat=True))

        def delete_then_fail(*args, **kwargs):
            demo_contracts().delete()  # halb fertig ...
            raise RuntimeError("Datenbank weg")  # ... und dann der Fehler

        day = date(2026, 11, 20)
        with mock.patch("apps.core.demo_refresh.call_command", side_effect=delete_then_fail):
            with self.assertLogs("apps.core.demo_refresh", level="ERROR"):
                result = refresh_demo_data_if_due(self.demo, today=day)

        self.assertFalse(result)
        self.assertEqual(
            set(demo_contracts().values_list("pk", flat=True)),
            contracts_before,
            "die Transaktion macht es rückgängig",
        )
        self.assertEqual(cache.get(_lock_key(day)), "failed")
        self.assertEqual(RETRY_SECONDS, 600)
        cache.delete(_lock_key(day))  # die zehn Minuten sind um
        retry, _seed = self.refresh(self.demo, day)
        self.assertTrue(retry, "nach dem Fehler gibt es einen neuen Versuch, nicht erst morgen")


class NoDemoAccountsTest(TestCase):
    """Ohne Demo-Konten (Entwicklung, Test, eine andere Umgebung) darf die Auffrischung nie eine Demo anlegen: Die Konten haben ein
    öffentliches Passwort."""

    def setUp(self):
        cache.clear()

    def test_it_never_creates_a_demo_where_there_is_none(self):
        normal = User.objects.create_user("normal", password="pw")
        self.assertFalse(User.objects.filter(username__in=["demo_premium", "demo_user"]).exists())

        with mock.patch("apps.core.demo_refresh.call_command") as seed:
            result = refresh_demo_data_if_due(normal, today=date(2026, 11, 20))

        self.assertFalse(result)
        seed.assert_not_called()
        self.assertFalse(User.objects.filter(username__in=["demo_premium", "demo_user"]).exists())

    def test_a_request_of_an_ordinary_visitor_creates_nothing_either(self):
        normal = User.objects.create_user("normal", password="pw", email="n@example.com")
        UserProfile.objects.create(user=normal, subscription_tier="pro")
        self.client.force_login(normal)

        self.client.get(reverse("core:dashboard"))
        self.client.get("/")

        self.assertFalse(User.objects.filter(username__in=["demo_premium", "demo_user"]).exists())


class MiddlewareTest(TestCase):
    def setUp(self):
        cache.clear()
        seed_on(date(2025, 11, 1), "--refresh")

    def upcoming(self, username):
        from django.utils import timezone

        return Lesson.objects.filter(
            contract__user__username=username, date__gt=timezone.localdate()
        ).count()

    def test_the_first_visit_of_a_demo_account_brings_the_demo_up_to_date(self):
        self.assertEqual(
            self.upcoming("demo_premium"), 0, "Ausgangslage: alles liegt in der Vergangenheit"
        )
        self.client.force_login(User.objects.get(username="demo_premium"))

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertGreater(self.upcoming("demo_premium"), 0)
        self.assertEqual(
            response.context["user"].pk,
            User.objects.get(username="demo_premium").pk,
            "der Login bleibt gültig",
        )

    def test_the_second_visit_of_the_day_does_not_start_over(self):
        self.client.force_login(User.objects.get(username="demo_premium"))
        self.client.get(reverse("core:dashboard"))
        marker = Contract.objects.create(
            user=User.objects.get(username="demo_premium"),
            first_name="Marker",
            last_name="Heute",
            hourly_rate=Decimal("20.00"),
            unit_duration_minutes=60,
            start_date=date(2026, 11, 1),
        )

        self.client.get(reverse("core:dashboard"))

        self.assertTrue(
            Contract.objects.filter(pk=marker.pk).exists(),
            "ein zweiter Zugriff am selben Tag lässt die Daten stehen",
        )

    def test_visitors_without_a_demo_account_change_nothing(self):
        normal = User.objects.create_user("normal", password="pw", email="n@example.com")
        UserProfile.objects.create(user=normal, subscription_tier="pro")
        before = set(demo_lessons().values_list("pk", flat=True))

        self.client.get("/")  # anonym
        self.client.force_login(normal)
        self.client.get(reverse("core:dashboard"))

        self.assertEqual(set(demo_lessons().values_list("pk", flat=True)), before)

    def test_a_failing_refresh_never_breaks_the_page(self):
        self.client.force_login(User.objects.get(username="demo_premium"))

        with mock.patch("apps.core.demo_refresh.call_command", side_effect=RuntimeError("kaputt")):
            with self.assertLogs("apps.core.demo_refresh", level="ERROR"):
                response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)


class RecurringSeriesStillWorkTest(TestCase):
    def test_the_series_are_long_enough_to_survive_a_missed_day(self):
        seed_on(date(2026, 11, 20), "--refresh")

        for series in RecurringLesson.objects.all():
            length = (series.end_date - series.start_date).days
            self.assertGreaterEqual(
                length,
                48,
                "mindestens sieben Wochen: Eine ausgefallene Auffrischung leert die Demo nicht sofort",
            )
