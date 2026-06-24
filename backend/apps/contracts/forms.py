from django import forms
from django.utils.translation import gettext_lazy as _

from apps.contracts.models import Contract


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
        self.fields["email"].label = _("Kontakt-E-Mail (Elternteil oder Schüler)")
        self.fields["email"].help_text = _(
            "Diese E-Mail-Adresse erhält alle Benachrichtigungen. Bei minderjährigen Schülern bitte die E-Mail-Adresse der Eltern angeben."
        )
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
