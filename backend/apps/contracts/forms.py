"""
Forms für Contract-Model.
"""

from apps.contracts.models import Contract
from django import forms
from django.utils.translation import gettext_lazy as _


class ContractForm(forms.ModelForm):
    """Form für Contract-Erstellung und -Bearbeitung."""

    has_monthly_planning_limit = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Monthly planning with planned units"),
        help_text=_(
            "If checked, you must enter planned units for each month. If unchecked, no maximum number of units is planned."
        ),
    )

    class Meta:
        model = Contract
        fields = [
            "student",
            "institute",
            "hourly_rate",
            "unit_duration_minutes",
            "start_date",
            "end_date",
            "is_active",
            "has_monthly_planning_limit",
            "notes",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "institute": forms.TextInput(attrs={"class": "form-control"}),
            "hourly_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "unit_duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "has_monthly_planning_limit": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
