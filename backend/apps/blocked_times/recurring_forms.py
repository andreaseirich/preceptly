"""
Forms für RecurringBlockedTime-Model.
"""

from apps.blocked_times.recurring_models import RecurringBlockedTime
from django import forms


class RecurringBlockedTimeForm(forms.ModelForm):
    """Form für RecurringBlockedTime-Erstellung und -Bearbeitung."""

    class Meta:
        model = RecurringBlockedTime
        fields = [
            "title",
            "description",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "recurrence_type",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "start_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}, format="%H:%M"
            ),
            "end_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}, format="%H:%M"
            ),
            "recurrence_type": forms.Select(attrs={"class": "form-control"}),
            "monday": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tuesday": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "wednesday": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "thursday": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "friday": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "saturday": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "sunday": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
