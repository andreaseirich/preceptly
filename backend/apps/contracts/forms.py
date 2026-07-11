from django import forms
from django.utils.translation import gettext_lazy as _

from apps.contracts.models import Contract, InstituteTierConfig


def _validate_tiers(tiers):
    """Validate the tiers data structure for InstituteTierConfig."""
    if not isinstance(tiers, list) or not tiers:
        return _("Tier list must be a non-empty list.")
    for t in tiers:
        if not isinstance(t, dict):
            return _("Each tier must be an object.")
        hours_from = t.get("hours_from")
        if not isinstance(hours_from, (int, float)) or hours_from < 0:
            return _("hours_from must be a non-negative number.")
        label = t.get("label", "")
        if not isinstance(label, str) or len(label) > 50:
            return _("Tier label must be a string with at most 50 characters.")
        if any(c in label for c in ("<", ">")):
            return _("Tier label contains invalid characters.")
    return None


class TierConfigForm(forms.ModelForm):
    class Meta:
        model = InstituteTierConfig
        fields = ["institute_name", "tiers"]

    def clean_tiers(self):
        tiers = self.cleaned_data.get("tiers")
        error = _validate_tiers(tiers)
        if error:
            raise forms.ValidationError(error)
        return tiers


class ContractForm(forms.ModelForm):
    """Form für Contract-Erstellung und -Bearbeitung (inkl. Schülerdaten)."""

    has_monthly_planning_limit = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Monatliche Planung mit geplanten Einheiten"),
    )

    class Meta:
        model = Contract
        fields = [
            "first_name",
            "last_name",
            "email",
            "parent_email",
            "phone",
            "school",
            "grade",
            "subjects",
            "is_adult",
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
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "parent_email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "school": forms.TextInput(attrs={"class": "form-control"}),
            "grade": forms.TextInput(attrs={"class": "form-control"}),
            "subjects": forms.TextInput(attrs={"class": "form-control"}),
            "is_adult": forms.CheckboxInput(attrs={"class": "form-check-input"}),
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = _("Schüler-E-Mail")
        self.fields["email"].help_text = _(
            "E-Mail-Adresse des Schülers — wird für das Schüler-Portal verwendet."
        )
        self.fields["parent_email"].label = _("Eltern-E-Mail")
        self.fields["parent_email"].help_text = _(
            "E-Mail-Adresse der Eltern — wird für das Eltern-Portal verwendet."
        )
        self.fields["parent_email"].required = False
        self._user = user

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self._user and not instance.pk:
            instance.user = self._user
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(_("End date must not be before start date."))
        return cleaned_data
