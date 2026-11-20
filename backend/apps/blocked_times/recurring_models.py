"""Datenhalter für eine Serie von Blockzeiten (Serientermin), nur im Speicher.

Früher war das ein Django-Modell mit eigener Tabelle. Die Tabelle wurde mit der Migration 0008 gelöscht; Serien entstehen seitdem direkt als
einzelne `BlockedTime`-Einträge. Die Klasse blieb als Datenhalter für `RecurringBlockedTimeService`: Die Ansicht baut beim Anlegen einer Serie
ein nicht gespeichertes Objekt und übergibt es dem Dienst.

Das darf kein `models.Model` sein. Als Modell kennt Django den Fremdschlüssel auf den Nutzer, und sobald die Klasse einmal importiert wurde
(die Ansicht tut das bei jedem Anlegen einer Blockzeit), will `User.delete()` danach aus der nicht mehr vorhandenen Tabelle löschen und
scheitert mit "no such table". In der Produktion traf das jeden Prozess, der seit dem Start eine Blockzeit angelegt hatte, etwa beim Löschen
eines Schülers mit Portal-Konto. In der Gesamtsuite traf es jeden Test, der danach einen Nutzer löschte. Siehe
`test_recurring_holder.py`.
"""

from dataclasses import dataclass
from datetime import date, time

from django.utils.translation import gettext_lazy as _


@dataclass
class RecurringBlockedTime:
    """Vorlage einer Serie von Blockzeiten. Wird nie gespeichert (es gibt keine Tabelle)."""

    user: object
    title: str
    start_date: date
    start_time: time
    end_time: time
    description: str | None = None
    end_date: date | None = None
    recurrence_type: str = "weekly"  # "weekly", "biweekly" oder "monthly"
    monday: bool = False
    tuesday: bool = False
    wednesday: bool = False
    thursday: bool = False
    friday: bool = False
    saturday: bool = False
    sunday: bool = False
    is_active: bool = True

    def __str__(self):
        weekdays = self.get_active_weekdays_display()
        return f"{self.title} - {weekdays} {self.start_time} (from {self.start_date})"

    def get_active_weekdays(self):
        """Returns a list of active weekdays (0=Monday, 6=Sunday)."""
        flags = (
            self.monday,
            self.tuesday,
            self.wednesday,
            self.thursday,
            self.friday,
            self.saturday,
            self.sunday,
        )
        return [index for index, active in enumerate(flags) if active]

    def get_active_weekdays_display(self):
        """Returns a human-readable representation of active weekdays."""
        weekday_names = [_("Mo"), _("Tu"), _("We"), _("Th"), _("Fr"), _("Sa"), _("Su")]
        active = [str(weekday_names[i]) for i in self.get_active_weekdays()]
        return ", ".join(active) if active else str(_("None"))
