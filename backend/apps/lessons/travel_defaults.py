"""Standard-Fahrzeiten je Schüler: bei neuen Stunden und Serien vorbelegt.

Der Vertrag trägt die Standardwerte (Contract.default_travel_time_*). Beim Anlegen einer Stunde oder Serie
füllt das Formular die Fahrzeitfelder damit, und ein kleines Skript (static/js/travel-defaults.js) füllt sie
neu, sobald der Tutor einen anderen Schüler wählt. Jede Stunde behält ihre eigenen Werte: Der Tutor kann sie
im Formular ändern, und eine spätere Änderung am Vertrag lässt bestehende Stunden unberührt.

Stunden, die Familien im Portal buchen, übernehmen die Standardwerte (apps/portal/views.py).
"""

from django.utils.translation import gettext_lazy as _


class TravelDefaultsMixin:
    """Für ModelForms mit den Feldern contract, travel_time_before_minutes und travel_time_after_minutes."""

    def setup_travel_defaults(self):
        rows = self.fields["contract"].queryset.values_list(
            "pk", "default_travel_time_before_minutes", "default_travel_time_after_minutes"
        )
        # Wird im Template mit json_script ausgegeben. Nur Verträge des Tutors (das Queryset ist
        # schon auf ihn eingeschränkt).
        self.contract_travel_defaults = {
            str(pk): {"before": before, "after": after} for pk, before, after in rows
        }

        if self.instance.pk:
            return  # bestehende Stunde oder Serie: ihre eigenen Werte bleiben
        help_text = _("Pre-filled from the student's contract; you can change it for this lesson.")
        self.fields["travel_time_before_minutes"].help_text = help_text
        self.fields["travel_time_after_minutes"].help_text = help_text
        if self.is_bound:
            return  # nach einem Fehler im Formular zählen die Eingaben des Tutors
        # Das Skript füllt die Felder beim Wechsel des Schülers neu.
        self.fields["contract"].widget.attrs["data-travel-prefill"] = "true"
        chosen = self.initial.get("contract")
        defaults = self.contract_travel_defaults.get(str(getattr(chosen, "pk", chosen)))
        if defaults:
            self.initial["travel_time_before_minutes"] = defaults["before"]
            self.initial["travel_time_after_minutes"] = defaults["after"]
