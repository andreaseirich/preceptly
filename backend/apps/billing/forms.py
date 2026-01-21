"""
Forms for billing app.
"""

from apps.billing.models import Invoice
from apps.contracts.models import Contract
from django import forms
from django.utils.translation import gettext_lazy as _


class InvoiceCreateForm(forms.Form):
    """
    Form for creating an invoice - automatically selects all lessons in the period.

    All taught lessons (status TAUGHT) in the period are automatically included.
    Lessons with status PLANNED or PAID are not considered.
    A lesson can only appear in one invoice.
    """

    period_start = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        help_text=_("Start of the billing period"),
    )
    period_end = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        help_text=_("End of the billing period"),
    )
    contract = forms.ModelChoiceField(
        queryset=Contract.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text=_(
            "Optional: Filter by contract (only lessons from this contract will be billed)"
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        period_start = cleaned_data.get("period_start")
        period_end = cleaned_data.get("period_end")

        if period_start and period_end and period_start > period_end:
            raise forms.ValidationError(_("The end date must not be before the start date."))

        return cleaned_data


class InvoiceForm(forms.ModelForm):
    """Form for invoice editing."""

    class Meta:
        model = Invoice
        fields = ["payer_name", "payer_address", "status"]
        widgets = {
            "payer_name": forms.TextInput(attrs={"class": "form-control"}),
            "payer_address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }
