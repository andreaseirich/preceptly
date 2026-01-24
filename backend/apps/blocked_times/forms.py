"""
Forms für BlockedTime-Model.
"""

from apps.blocked_times.models import BlockedTime
from django import forms
from django.utils.translation import gettext_lazy as _


class BlockedTimeForm(forms.ModelForm):
    """Form für BlockedTime-Erstellung und -Bearbeitung."""

    # Option für Bearbeitung: nur diese Blockzeit oder ganze Serie
    edit_scope = forms.ChoiceField(
        required=False,
        initial="single",
        choices=[
            ("single", _("Edit only this blocked time")),
            ("series", _("Edit entire series")),
        ],
        label=_("Edit scope"),
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    # Recurrence fields (only shown when creating, not editing)
    is_recurring = forms.BooleanField(
        required=False,
        label=_("Repeat this blocked time"),
        help_text=_("Create a recurring series instead of a single blocked time"),
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
        help_text=_("Select weekdays for the recurring blocked time"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = BlockedTime
        fields = [
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "is_recurring",
            "recurring_pattern",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "start_datetime": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "end_datetime": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "is_recurring": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "recurring_pattern": forms.TextInput(attrs={"class": "form-control"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide recurrence fields when editing (only show when creating)
        if self.instance and self.instance.pk:
            self.fields["is_recurring"].widget = forms.HiddenInput()
            self.fields["recurrence_type"].widget = forms.HiddenInput()
            self.fields["recurrence_end_date"].widget = forms.HiddenInput()
            
            # Prüfe, ob diese BlockedTime zu einer Serie gehört
            from apps.blocked_times.recurring_utils import find_matching_recurring_blocked_time
            
            matching_recurring = find_matching_recurring_blocked_time(self.instance)
            if matching_recurring:
                # Zeige Option für Bearbeitungsscope
                self.fields["edit_scope"].initial = "single"
                # Wenn Serie bearbeitet wird, zeige Wochentage-Felder
                # Initialisiere mit aktuellen Wochentagen der Serie
                active_weekdays = matching_recurring.get_active_weekdays()
                self.fields["recurrence_weekdays"].initial = [str(wd) for wd in active_weekdays]
                # Widget immer sichtbar machen - wird per JavaScript gesteuert
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
    
    def clean(self):
        """Validiere Recurrence-Felder."""
        cleaned_data = super().clean()
        
        is_recurring = cleaned_data.get("is_recurring", False)
        
        if is_recurring:
            recurrence_type = cleaned_data.get("recurrence_type")
            recurrence_weekdays = cleaned_data.get("recurrence_weekdays", [])
            
            if not recurrence_type:
                raise forms.ValidationError(_("Please select a repeat pattern when creating a recurring blocked time."))
            
            if not recurrence_weekdays:
                raise forms.ValidationError(_("Please select at least one weekday when creating a recurring blocked time."))
        
        return cleaned_data
