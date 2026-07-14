"""
Views for contract CRUD operations.
"""

from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.contracts.forms import ContractForm, InstituteForm
from apps.contracts.formsets import (
    ContractMonthlyPlanFormSet,
    generate_monthly_plans_for_contract,
    iter_contract_months,
)
from apps.contracts.models import Contract, ContractMonthlyPlan, Institute
from apps.contracts.services import (
    get_contract_current_month_summary,
    get_contract_monthly_planning_summary,
    get_institute_tier_progress,
)
from apps.core.demo_guard import DEMO_CONTRACT_LIMIT, demo_block, is_demo_user


class ContractListView(LoginRequiredMixin, ListView):
    """List of all contracts for the current user."""

    model = Contract
    template_name = "contracts/contract_list.html"
    context_object_name = "contracts"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contracts = list(context.get("contracts", []))
        context["contract_list_with_summary"] = [
            {
                "contract": c,
                "current_month_summary": get_contract_current_month_summary(c)
                if c.is_active
                else None,
            }
            for c in contracts
        ]
        context["family_suggestions"] = self._detect_family_suggestions()
        return context

    def _detect_family_suggestions(self):
        """Findet Vertragspaare, die vermutlich zur selben Familie gehören
        (gleicher Nachname oder gleiche Kontakt-E-Mail), aber noch keinen
        gemeinsamen Portal-Account haben."""
        from apps.portal.models import ParentStudentLink

        all_contracts = list(Contract.objects.filter(user=self.request.user))
        if len(all_contracts) < 2:
            return []

        # Auch noch nicht aktivierte Einladungen zählen als "schon verknüpft",
        # damit bereits eingeladene/verknüpfte Paare nicht weiter vorgeschlagen werden.
        links = ParentStudentLink.objects.filter(contract__user=self.request.user).values_list(
            "contract_id", "parent_id"
        )
        linked_accounts = {}
        for contract_id, parent_id in links:
            linked_accounts.setdefault(contract_id, set()).add(parent_id)

        suggestions = []
        for i, a in enumerate(all_contracts):
            for b in all_contracts[i + 1 :]:
                shared_account = linked_accounts.get(a.pk, set()) & linked_accounts.get(b.pk, set())
                if shared_account:
                    continue
                same_name = bool(
                    a.last_name.strip()
                    and a.last_name.strip().lower() == b.last_name.strip().lower()
                )
                a_emails = {e.lower() for e in [a.email, a.parent_email] if e}
                b_emails = {e.lower() for e in [b.email, b.parent_email] if e}
                same_email = bool(a_emails & b_emails)
                if same_name or same_email:
                    suggestions.append(
                        {
                            "a": a,
                            "b": b,
                            "reason": "email" if same_email else "name",
                        }
                    )
        return suggestions


class ContractDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a contract."""

    model = Contract
    template_name = "contracts/contract_detail.html"
    context_object_name = "contract"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        from apps.portal.models import ParentStudentLink, PortalMessage, ProgressNote

        context = super().get_context_data(**kwargs)
        contract = context["contract"]
        if contract.is_active and contract.has_monthly_planning_limit:
            context["monthly_planning_summary"] = get_contract_monthly_planning_summary(
                contract, year=date.today().year
            )
        else:
            context["monthly_planning_summary"] = []
        portal_links = list(
            ParentStudentLink.objects.filter(contract=contract).select_related("parent__user")
        )
        site_url = getattr(settings, "SITE_URL", "https://preceptly.de")
        for link in portal_links:
            if not link.is_active:
                link.activation_url = f"{site_url}/portal/activate/{link.invite_token}/"
        context["portal_links"] = portal_links
        context["progress_notes"] = ProgressNote.objects.filter(contract=contract).order_by(
            "-created_at"
        )[:10]
        context["unread_messages"] = PortalMessage.objects.filter(
            contract=contract, read_by_tutor=False
        ).count()
        return context


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
        if is_demo_user(self.request.user):
            count = Contract.objects.filter(user=self.request.user).count()
            if count >= DEMO_CONTRACT_LIMIT:
                from django.utils.translation import gettext as _t

                return demo_block(
                    self.request,
                    _t("Demo limit reached: max {n} contracts per demo account.").format(
                        n=DEMO_CONTRACT_LIMIT
                    ),
                )
        # Save contract first
        form.instance.user = self.request.user
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
        return super().get_queryset().filter(user=self.request.user)

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
        with transaction.atomic():
            # Direkt das Formset instanziieren, ohne get_context_data() aufzurufen
            has_limit = self.request.POST.get("has_monthly_planning_limit", "on") == "on"
            if has_limit:
                formset = ContractMonthlyPlanFormSet(self.request.POST, instance=self.object)
            else:
                formset = None

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
        return super().get_queryset().filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Contract successfully deleted."))
        return super().delete(request, *args, **kwargs)


class InstituteListView(LoginRequiredMixin, ListView):
    """Manage institutes: tiered pay, no-show rule, tier progress — all in one place."""

    model = Institute
    template_name = "contracts/institute_list.html"
    context_object_name = "institutes"

    def get_queryset(self):
        return Institute.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for institute in context["institutes"]:
            institute.tier_progress = get_institute_tier_progress(institute)
        return context


class InstituteCreateView(LoginRequiredMixin, CreateView):
    model = Institute
    form_class = InstituteForm
    template_name = "contracts/institute_form.html"
    success_url = reverse_lazy("contracts:institute_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, _("Institute saved."))
        return response


class InstituteUpdateView(LoginRequiredMixin, UpdateView):
    model = Institute
    form_class = InstituteForm
    template_name = "contracts/institute_form.html"
    success_url = reverse_lazy("contracts:institute_list")

    def get_queryset(self):
        return Institute.objects.filter(user=self.request.user)

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, _("Institute saved."))
        return response


class InstituteDeleteView(LoginRequiredMixin, DeleteView):
    model = Institute
    template_name = "contracts/institute_confirm_delete.html"
    success_url = reverse_lazy("contracts:institute_list")

    def get_queryset(self):
        return Institute.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        from django.db.models import ProtectedError

        try:
            response = super().delete(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _(
                    "This institute cannot be deleted because contracts are still assigned "
                    "to it. Reassign or remove those contracts first."
                ),
            )
            return redirect("contracts:institute_list")
        messages.success(request, _("Institute deleted."))
        return response


class ContractToggleActiveView(LoginRequiredMixin, View):
    """Toggle a contract's is_active flag without entering the edit form."""

    http_method_names = ["post"]

    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        contract.is_active = not contract.is_active
        contract.save(update_fields=["is_active"])
        if contract.is_active:
            messages.success(request, _("Activated"))
        else:
            messages.success(request, _("Deactivated"))
        return redirect("contracts:list")
