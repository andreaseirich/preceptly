"""
Forms für BlockedTime-Model.
"""

from apps.blocked_times.models import BlockedTime
from django import forms


class BlockedTimeForm(forms.ModelForm):
    """Form für BlockedTime-Erstellung und -Bearbeitung."""

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
