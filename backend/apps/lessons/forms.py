"""
Forms für Lesson-Model.
"""

from apps.lessons.models import Lesson
from django import forms
from django.utils.translation import gettext_lazy as _


class LessonForm(forms.ModelForm):
    """Form für Lesson-Erstellung und -Bearbeitung."""

    # Option für Bearbeitung: nur diese Stunde oder ganze Serie
    edit_scope = forms.ChoiceField(
        required=False,
        choices=[
            ("single", _("Edit only this lesson")),
            ("series", _("Edit entire series")),
        ],
        label=_("Edit scope"),
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    # Recurrence fields (only shown when creating, not editing)
    is_recurring = forms.BooleanField(
        required=False,
        label=_("Repeat this lesson"),
        help_text=_("Create a recurring series instead of a single lesson"),
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "onchange": "toggleRecurrenceFields()"}
        ),
    )
    recurrence_type = forms.ChoiceField(
        required=False,
        choices=[
            ("", _("None")),
            ("weekly", _("Weekly")),
            ("biweekly", _("Every 2 Weeks")),
            ("monthly", _("Monthly")),
        ],
        label=_("Repeat pattern"),
        widget=forms.Select(attrs={"class": "form-control", "style": "display: none;"}),
    )
    recurrence_end_date = forms.DateField(
        required=False,
        label=_("End date"),
        help_text=_("When should the series end? (optional)"),
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "style": "display: none;"}
        ),
    )
    recurrence_weekdays = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("0", _("Monday")),
            ("1", _("Tuesday")),
            ("2", _("Wednesday")),
            ("3", _("Thursday")),
            ("4", _("Friday")),
            ("5", _("Saturday")),
            ("6", _("Sunday")),
        ],
        label=_("Weekdays"),
        help_text=_("Select weekdays for the recurring lesson"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Lesson
        fields = [
            "contract",
            "date",
            "start_time",
            "duration_minutes",
            "travel_time_before_minutes",
            "travel_time_after_minutes",
            "notes",
        ]
        widgets = {
            "contract": forms.Select(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "travel_time_before_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "travel_time_after_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide recurrence fields when editing (only show when creating)
        if self.instance and self.instance.pk:
            self.fields["is_recurring"].widget = forms.HiddenInput()
            self.fields["recurrence_type"].widget = forms.HiddenInput()
            self.fields["recurrence_end_date"].widget = forms.HiddenInput()
            
            # Prüfe, ob diese Lesson zu einer Serie gehört
            from apps.lessons.recurring_utils import find_matching_recurring_lesson
            
            matching_recurring = find_matching_recurring_lesson(self.instance)
            if matching_recurring:
                # Zeige Option für Bearbeitungsscope
                self.fields["edit_scope"].initial = "single"
                # Wenn Serie bearbeitet wird, zeige Wochentage-Felder
                # Initialisiere mit aktuellen Wochentagen der Serie
                active_weekdays = matching_recurring.get_active_weekdays()
                self.fields["recurrence_weekdays"].initial = [str(wd) for wd in active_weekdays]
                # Widget immer sichtbar machen - wird per JavaScript gesteuert
                # WICHTIG: Kein HiddenInput, damit Checkboxes gerendert werden
                self.fields["recurrence_weekdays"].widget = forms.CheckboxSelectMultiple(
                    attrs={"class": "form-check-input"}
                )
            else:
                # Verstecke edit_scope und recurrence_weekdays, wenn keine Serie gefunden
                self.fields["edit_scope"].widget = forms.HiddenInput()
                self.fields["recurrence_weekdays"].widget = forms.HiddenInput()
        else:
            # Beim Erstellen: edit_scope verstecken
            self.fields["edit_scope"].widget = forms.HiddenInput()