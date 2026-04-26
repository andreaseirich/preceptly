"""
Formsets für ContractMonthlyPlan.
"""

from datetime import date

from django import forms
from django.forms import inlineformset_factory

from apps.contracts.models import Contract, ContractMonthlyPlan


class ContractMonthlyPlanForm(forms.ModelForm):
    """Form für einen einzelnen ContractMonthlyPlan-Eintrag."""

    class Meta:
        model = ContractMonthlyPlan
        fields = ["year", "month", "planned_units"]
        widgets = {
            "year": forms.NumberInput(attrs={"class": "form-control", "readonly": True}),
            "month": forms.NumberInput(attrs={"class": "form-control", "readonly": True}),
            "planned_units": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }


ContractMonthlyPlanFormSet = inlineformset_factory(
    Contract,
    ContractMonthlyPlan,
    form=ContractMonthlyPlanForm,
    extra=0,
    can_delete=False,
    fields=["year", "month", "planned_units"],
)


def iter_contract_months(start_date: date, end_date: date = None) -> list:
    """
    Iteriert über alle Monate zwischen start_date und end_date.

    Args:
        start_date: Startdatum des Vertrags
        end_date: Enddatum des Vertrags (optional, None = unbefristet)
                 Falls None, wird ein Standard-Zeitraum von 5 Jahren ab start_date verwendet
                 (genau 60 Monate: vom Startmonat bis zum letzten Monat des 5. Jahres)

    Returns:
        Liste von (year, month) Tupeln für alle Monate im Intervall
    """
    if not start_date:
        return []

    # Für unbefristete Verträge: Standard-Zeitraum von genau 5 Jahren (60 Monate)
    if end_date is None:
        # Setze Enddatum auf den letzten Tag des 5. Jahres
        end_year = start_date.year + 4  # 5 Jahre = Jahr 0-4
        end_month = 12
        end_date = date(end_year, end_month, 31)

    months = []
    current_year = start_date.year
    current_month = start_date.month
    end_year = end_date.year
    end_month = end_date.month

    while (current_year, current_month) <= (end_year, end_month):
        months.append((current_year, current_month))

        # Nächster Monat
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return months


def generate_monthly_plans_for_contract(contract: Contract) -> list:
    """
    Generiert ContractMonthlyPlan-Einträge für alle Monate im Vertragszeitraum.

    Die Monate werden unabhängig vom aktuellen Datum erzeugt - für den gesamten
    Zeitraum zwischen start_date und end_date (oder 5 Jahre bei unbefristeten Verträgen).

    Args:
        contract: Der Contract, für den die Pläne erstellt werden sollen

    Returns:
        Liste der erstellten ContractMonthlyPlan-Objekte
    """
    if not contract.start_date:
        return []

    plans = []
    months = iter_contract_months(contract.start_date, contract.end_date)

    for year, month in months:
        # Prüfe, ob bereits ein Plan für diesen Monat existiert
        plan, created = ContractMonthlyPlan.objects.get_or_create(
            contract=contract, year=year, month=month, defaults={"planned_units": 0}
        )
        plans.append(plan)

    return plans
