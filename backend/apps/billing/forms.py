"""
Forms for billing app.
"""

from apps.billing.models import Invoice
from apps.contracts.models import Contract
from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


def _get_institute_choices_for_user(user):
    """Return choices for institute filter: empty + distinct institutes from user's contracts."""
    if not user:
        return [("", _("All institutes"))]
    institutes = (
        Contract.objects.filter(student__user=user, is_active=True)
        .exclude(Q(institute__isnull=True) | Q(institute=""))
        .values_list("institute", flat=True)
        .distinct()
        .order_by("institute")
    )
    return [("", _("All institutes"))] + [(i, i) for i in institutes]


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
    institute = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        choices=[("", _("All institutes"))],
        help_text=_(
            "Optional: Filter by institute (only lessons from contracts with this institute)"
        ),
    )
    contract = forms.ModelChoiceField(
        queryset=Contract.objects.none(),  # Set in __init__ based on user
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text=_(
            "Optional: Filter by contract (only lessons from this contract will be billed)"
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["institute"].choices = _get_institute_choices_for_user(user)
            base_contracts = Contract.objects.filter(is_active=True, student__user=user)
            institute = self.initial.get("institute") or (
                self.data.get("institute") if self.data else None
            )
            if institute:
                base_contracts = base_contracts.filter(institute=institute)
            self.fields["contract"].queryset = base_contracts

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
