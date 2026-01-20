"""
Views for contract CRUD operations.
"""

from apps.contracts.forms import ContractForm
from apps.contracts.formsets import (
    ContractMonthlyPlanFormSet,
    generate_monthly_plans_for_contract,
    iter_contract_months,
)
from apps.contracts.models import Contract, ContractMonthlyPlan
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class ContractListView(LoginRequiredMixin, ListView):
    """List of all contracts."""

    model = Contract
    template_name = "contracts/contract_list.html"
    context_object_name = "contracts"
    paginate_by = 20


class ContractDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a contract."""

    model = Contract
    template_name = "contracts/contract_detail.html"
    context_object_name = "contract"


class ContractCreateView(LoginRequiredMixin, CreateView):
    """Create a new contract."""

    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"
    success_url = reverse_lazy("contracts:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Formset nur anzeigen, wenn has_monthly_planning_limit aktiviert ist
        if self.request.POST:
            # Prüfe den POST-Wert direkt
            has_limit = self.request.POST.get("has_monthly_planning_limit", "on") == "on"
            if has_limit:
                context["formset"] = ContractMonthlyPlanFormSet(self.request.POST)
            else:
                context["formset"] = None
        else:
            # Initial: Formset ist leer, wird nach Speichern des Contracts gefüllt
            # Standardmäßig ist has_monthly_planning_limit aktiviert
            context["formset"] = ContractMonthlyPlanFormSet()
        return context

    def form_valid(self, form):
        # Speichere Contract zuerst
        self.object = form.save()

        # Nur monatliche Pläne generieren, wenn has_monthly_planning_limit aktiviert ist
        if self.object.has_monthly_planning_limit and self.object.start_date:
            generate_monthly_plans_for_contract(self.object)
            # Weiterleitung zur Update-View, um monatliche Planung zu bearbeiten
            messages.success(
                self.request,
                _("Contract created. Please enter the planned units per month."),
            )
            return redirect("contracts:update", pk=self.object.pk)
        else:
            messages.success(self.request, _("Contract successfully created."))
            return redirect(self.success_url)


class ContractUpdateView(LoginRequiredMixin, UpdateView):
    """Update a contract."""

    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"
    success_url = reverse_lazy("contracts:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Formset nur anzeigen, wenn has_monthly_planning_limit aktiviert ist
        if self.request.POST:
            # Prüfe den POST-Wert direkt
            has_limit = self.request.POST.get("has_monthly_planning_limit", "on") == "on"
            if has_limit:
                context["formset"] = ContractMonthlyPlanFormSet(self.request.POST, instance=self.object)
            else:
                context["formset"] = None
        else:
            # Lade vorhandene Pläne oder generiere neue, nur wenn has_monthly_planning_limit aktiviert ist
            if self.object.has_monthly_planning_limit and self.object.start_date:
                # Stelle sicher, dass alle Monate im Zeitraum abgedeckt sind
                generate_monthly_plans_for_contract(self.object)

                # Lösche Pläne außerhalb des Vertragszeitraums
                valid_months = set(
                    iter_contract_months(self.object.start_date, self.object.end_date)
                )
                ContractMonthlyPlan.objects.filter(contract=self.object).exclude(
                    year__in=[year for year, _ in valid_months]
                )

                # Filtere präzise: Nur Pläne, deren (year, month) nicht in valid_months ist
                for plan in ContractMonthlyPlan.objects.filter(contract=self.object):
                    if (plan.year, plan.month) not in valid_months:
                        plan.delete()

                context["formset"] = ContractMonthlyPlanFormSet(instance=self.object)
            else:
                # Wenn has_monthly_planning_limit deaktiviert ist, lösche alle vorhandenen Pläne
                if not self.object.has_monthly_planning_limit:
                    ContractMonthlyPlan.objects.filter(contract=self.object).delete()
                context["formset"] = None
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]

        # Speichere Contract
        self.object = form.save()

        # Nur monatliche Pläne verwalten, wenn has_monthly_planning_limit aktiviert ist
        if self.object.has_monthly_planning_limit:
            # Wenn Zeitraum geändert wurde, generiere neue Pläne
            if self.object.start_date:
                generate_monthly_plans_for_contract(self.object)

                # Lösche Pläne außerhalb des neuen Zeitraums
                valid_months = set(iter_contract_months(self.object.start_date, self.object.end_date))
                for plan in ContractMonthlyPlan.objects.filter(contract=self.object):
                    if (plan.year, plan.month) not in valid_months:
                        plan.delete()

            # Formset aktualisieren und speichern
            if formset:
                formset.instance = self.object
                if formset.is_valid():
                    formset.save()
                    messages.success(self.request, _("Contract successfully updated."))
                    return redirect(self.success_url)
                else:
                    messages.error(self.request, _("Please correct the errors in the monthly planning."))
                    return self.render_to_response(self.get_context_data(form=form, formset=formset))
        else:
            # Wenn has_monthly_planning_limit deaktiviert ist, lösche alle vorhandenen Pläne
            ContractMonthlyPlan.objects.filter(contract=self.object).delete()

        messages.success(self.request, _("Contract successfully updated."))
        return redirect(self.success_url)


class ContractDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a contract."""

    model = Contract
    template_name = "contracts/contract_confirm_delete.html"
    success_url = reverse_lazy("contracts:list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Contract successfully deleted."))
        return super().delete(request, *args, **kwargs)
