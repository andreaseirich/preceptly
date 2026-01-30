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
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class ContractListView(LoginRequiredMixin, ListView):
    """List of all contracts for the current user."""

    model = Contract
    template_name = "contracts/contract_list.html"
    context_object_name = "contracts"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(student__user=self.request.user)


class ContractDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a contract."""

    model = Contract
    template_name = "contracts/contract_detail.html"
    context_object_name = "contract"

    def get_queryset(self):
        return super().get_queryset().filter(student__user=self.request.user)


class ContractCreateView(LoginRequiredMixin, CreateView):
    """Create a new contract."""

    model = Contract
    form_class = ContractForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    template_name = "contracts/contract_form.html"
    success_url = reverse_lazy("contracts:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only show formset if has_monthly_planning_limit is enabled
        if self.request.POST:
            # Check POST value directly
            has_limit = self.request.POST.get("has_monthly_planning_limit", "on") == "on"
            if has_limit:
                context["formset"] = ContractMonthlyPlanFormSet(self.request.POST)
            else:
                context["formset"] = None
        else:
            # Initial: formset is empty, will be filled after saving the contract
            # By default, has_monthly_planning_limit is enabled
            context["formset"] = ContractMonthlyPlanFormSet()
        return context

    def form_valid(self, form):
        # Save contract first
        self.object = form.save()

        # Only generate monthly plans if has_monthly_planning_limit is enabled
        if self.object.has_monthly_planning_limit and self.object.start_date:
            generate_monthly_plans_for_contract(self.object)
            # Redirect to update view to edit monthly planning
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

    def get_queryset(self):
        return super().get_queryset().filter(student__user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    template_name = "contracts/contract_form.html"
    success_url = reverse_lazy("contracts:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only show formset if has_monthly_planning_limit is enabled
        if self.request.POST:
            # Check POST value directly
            has_limit = self.request.POST.get("has_monthly_planning_limit", "on") == "on"
            if has_limit:
                context["formset"] = ContractMonthlyPlanFormSet(
                    self.request.POST, instance=self.object
                )
            else:
                context["formset"] = None
        else:
            # Load existing plans or generate new ones, only if has_monthly_planning_limit is enabled
            if self.object.has_monthly_planning_limit and self.object.start_date:
                # Ensure all months in the period are covered
                generate_monthly_plans_for_contract(self.object)

                # Delete plans outside the contract period
                valid_months = set(
                    iter_contract_months(self.object.start_date, self.object.end_date)
                )
                ContractMonthlyPlan.objects.filter(contract=self.object).exclude(
                    year__in=[year for year, _ in valid_months]
                )

                # Filter precisely: Only plans whose (year, month) is not in valid_months
                for plan in ContractMonthlyPlan.objects.filter(contract=self.object):
                    if (plan.year, plan.month) not in valid_months:
                        plan.delete()

                context["formset"] = ContractMonthlyPlanFormSet(instance=self.object)
            else:
                # If has_monthly_planning_limit is disabled, delete all existing plans
                if not self.object.has_monthly_planning_limit:
                    ContractMonthlyPlan.objects.filter(contract=self.object).delete()
                context["formset"] = None
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]

        # Save contract
        self.object = form.save()

        # Only manage monthly plans if has_monthly_planning_limit is enabled
        if self.object.has_monthly_planning_limit:
            # If period was changed, generate new plans
            if self.object.start_date:
                generate_monthly_plans_for_contract(self.object)

                # Delete plans outside the new period
                valid_months = set(
                    iter_contract_months(self.object.start_date, self.object.end_date)
                )
                for plan in ContractMonthlyPlan.objects.filter(contract=self.object):
                    if (plan.year, plan.month) not in valid_months:
                        plan.delete()

            # Update and save formset
            if formset:
                formset.instance = self.object
                if formset.is_valid():
                    formset.save()
                    messages.success(self.request, _("Contract successfully updated."))
                    return redirect(self.success_url)
                else:
                    messages.error(
                        self.request, _("Please correct the errors in the monthly planning.")
                    )
                    return self.render_to_response(
                        self.get_context_data(form=form, formset=formset)
                    )
        else:
            # If has_monthly_planning_limit is disabled, delete all existing plans
            ContractMonthlyPlan.objects.filter(contract=self.object).delete()

        messages.success(self.request, _("Contract successfully updated."))
        return redirect(self.success_url)


class ContractDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a contract."""

    model = Contract
    template_name = "contracts/contract_confirm_delete.html"
    success_url = reverse_lazy("contracts:list")

    def get_queryset(self):
        return super().get_queryset().filter(student__user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Contract successfully deleted."))
        return super().delete(request, *args, **kwargs)
