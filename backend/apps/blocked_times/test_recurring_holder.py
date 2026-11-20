"""Der Datenhalter für Serien von Blockzeiten darf kein Django-Modell sein.

Gefunden am 20.11.2026 beim Testen der Demo-Auffrischung. Die Tabelle `blocked_times_recurringblockedtime` ist seit Migration 0008 weg, die
Klasse `RecurringBlockedTime` blieb aber als Modell mit Fremdschlüssel auf den Nutzer. `BlockedTimeCreateView.form_valid` importiert sie bei
jedem Anlegen einer Blockzeit. Danach versuchte `User.delete()` im selben Prozess, aus der fehlenden Tabelle zu löschen: "no such table".
In der Produktion (ein langlebiger Prozess) traf das zum Beispiel das Löschen eines Schülers mit Portal-Konto, in der Gesamtsuite jeden Test,
der nach einem Blockzeiten-Test einen Nutzer löschte.
"""

from datetime import time, timedelta

from django.apps import apps
from django.contrib.auth.models import User
from django.db import models
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.blocked_times.models import BlockedTime
from apps.blocked_times.recurring_models import RecurringBlockedTime
from apps.blocked_times.recurring_service import RecurringBlockedTimeService
from apps.core.models import UserProfile


def next_monday():
    today = timezone.localdate()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def holder(user, **kwargs):
    defaults = {
        "user": user,
        "title": "Vorlesung",
        "start_date": next_monday(),
        "start_time": time(10, 0),
        "end_time": time(12, 0),
        "monday": True,
    }
    return RecurringBlockedTime(**{**defaults, **kwargs})


class HolderIsNotAModelTest(TestCase):
    def test_it_is_not_a_django_model(self):
        self.assertFalse(issubclass(RecurringBlockedTime, models.Model))
        self.assertEqual([m for m in apps.get_models() if m.__name__ == "RecurringBlockedTime"], [])

    def test_the_user_model_knows_no_relation_to_it(self):
        related = {rel.related_model.__name__ for rel in User._meta.related_objects}

        self.assertNotIn("RecurringBlockedTime", related)

    def test_deleting_a_user_still_works_after_a_blocked_time_series_was_created(self):
        tutor = User.objects.create_user("tutor_serie", password="pw")
        UserProfile.objects.update_or_create(user=tutor, defaults={"subscription_tier": "starter"})
        self.client.force_login(tutor)
        start = timezone.make_aware(
            timezone.datetime.combine(timezone.localdate() + timedelta(days=7), time(6, 0))
        )
        end = start + timedelta(hours=6)
        # Das Anlegen läuft durch form_valid und importiert die Klasse, wie in der Produktion
        response = self.client.post(
            reverse("blocked_times:create"),
            {
                "title": "Serie",
                "description": "",
                "start_datetime": start.strftime("%Y-%m-%dT%H:%M"),
                "end_datetime": end.strftime("%Y-%m-%dT%H:%M"),
                "is_recurring": "on",
                "recurrence_type": "weekly",
                "recurrence_end_date": (start + timedelta(days=14)).strftime("%Y-%m-%d"),
                "recurrence_weekdays": [str(start.weekday())],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertGreater(BlockedTime.objects.filter(user=tutor, title="Serie").count(), 0)
        victim = User.objects.create_user("opfer", password="pw")

        victim.delete()  # früher: OperationalError "no such table: blocked_times_recurringblockedtime"

        self.assertFalse(User.objects.filter(username="opfer").exists())


class HolderBehaviourTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("tutor_halter", password="pw")

    def test_the_weekdays_are_listed_as_numbers_and_as_text(self):
        series = holder(self.tutor, monday=True, wednesday=True, sunday=True)

        self.assertEqual(series.get_active_weekdays(), [0, 2, 6])
        self.assertEqual(series.get_active_weekdays_display().count(","), 2)
        self.assertTrue(
            holder(self.tutor, monday=False).get_active_weekdays_display(),
            "auch ohne Wochentag eine Anzeige",
        )

    def test_it_reads_as_text(self):
        self.assertIn("Vorlesung", str(holder(self.tutor)))

    def test_the_service_creates_one_blocked_time_per_matching_day(self):
        start = next_monday()
        series = holder(self.tutor, start_date=start, end_date=start + timedelta(days=14))

        result = RecurringBlockedTimeService.generate_blocked_times(series, check_conflicts=False)

        self.assertEqual(result["created"], 3, "drei Montage in 14 Tagen inklusive Start und Ende")
        days = sorted(b.start_datetime.date() for b in BlockedTime.objects.filter(user=self.tutor))
        self.assertEqual(days, [start, start + timedelta(days=7), start + timedelta(days=14)])

    def test_an_inactive_series_creates_nothing(self):
        result = RecurringBlockedTimeService.generate_blocked_times(
            holder(self.tutor, is_active=False)
        )

        self.assertEqual(result["created"], 0)
        self.assertFalse(BlockedTime.objects.filter(user=self.tutor).exists())

    def test_nothing_is_ever_written_to_a_table(self):
        series = holder(self.tutor)

        self.assertFalse(hasattr(series, "save"), "es gibt keine Tabelle, also auch kein save()")
        self.assertFalse(hasattr(RecurringBlockedTime, "objects"))
