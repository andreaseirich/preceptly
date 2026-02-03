"""
Views für Billing-App.
"""

from datetime import date

from apps.billing.document_service import InvoiceDocumentService
from apps.billing.forms import InvoiceCreateForm
from apps.billing.models import Invoice
from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import CreateView, DeleteView, DetailView, ListView


def _safe_date(val):
    """Parse ISO date or return None on invalid input."""
    if val is None:
        return None
    try:
        return date.fromisoformat(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val):
    """Parse int or return None on invalid input."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _user_invoice_queryset(user):
    """Invoices visible to the user (via contract or via items)."""
    return Invoice.objects.filter(
        Q(contract__student__user=user) | Q(items__lesson__contract__student__user=user)
    ).distinct()


class InvoiceListView(LoginRequiredMixin, ListView):
    """Liste aller Rechnungen."""

    model = Invoice
    template_name = "billing/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20

    def get_queryset(self):
        qs = _user_invoice_queryset(self.request.user)
        from apps.core.feature_flags import Feature, user_has_feature

        if user_has_feature(self.request.user, Feature.FEATURE_BILLING_PRO):
            status = self.request.GET.get("status", "").strip()
            if status in ("draft", "sent", "paid"):
                qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.core.feature_flags import Feature, user_has_feature

        context["is_billing_pro"] = user_has_feature(self.request.user, Feature.FEATURE_BILLING_PRO)
        context["status_filter"] = self.request.GET.get("status", "")
        return context


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer Rechnung."""

    model = Invoice
    template_name = "billing/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return _user_invoice_queryset(self.request.user)


class InvoiceCreateView(LoginRequiredMixin, CreateView):
    """Erstellung einer neuen Rechnung aus Lessons."""

    form_class = InvoiceCreateForm
    template_name = "billing/invoice_create.html"
    model = None  # Kein Model, da wir ein normales Form verwenden

    def get_form_kwargs(self):
        """Removes 'instance' from kwargs, as InvoiceCreateForm is not a ModelForm."""
        kwargs = super().get_form_kwargs()
        # Remove 'instance' if present (added by CreateView)
        kwargs.pop("instance", None)
        kwargs["user"] = self.request.user

        # If GET parameters are present (e.g., after preview), set initial values
        if self.request.method == "GET":
            initial = kwargs.get("initial", {})
            period_start = self.request.GET.get("period_start")
            period_end = self.request.GET.get("period_end")
            contract_id = self.request.GET.get("contract")
            institute = self.request.GET.get("institute")

            parsed_start = _safe_date(period_start)
            if parsed_start is not None:
                initial["period_start"] = parsed_start

            parsed_end = _safe_date(period_end)
            if parsed_end is not None:
                initial["period_end"] = parsed_end

            parsed_contract = _safe_int(contract_id)
            if parsed_contract is not None:
                initial["contract"] = parsed_contract

            if institute is not None and institute != "":
                initial["institute"] = institute

            if initial:
                kwargs["initial"] = initial

        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Load lessons for preview if period is present
        period_start = self.request.GET.get("period_start")
        period_end = self.request.GET.get("period_end")
        contract_id = self.request.GET.get("contract")
        institute = self.request.GET.get("institute") or None

        parsed_start = _safe_date(period_start)
        parsed_end = _safe_date(period_end)
        if parsed_start is not None and parsed_end is not None:
            contract = None
            parsed_contract_id = _safe_int(contract_id)
            if parsed_contract_id is not None:
                contract = Contract.objects.filter(
                    pk=parsed_contract_id, student__user=self.request.user
                ).first()

            billable_lessons = InvoiceService.get_billable_lessons(
                parsed_start,
                parsed_end,
                contract_id=parsed_contract_id,
                institute=institute,
                user=self.request.user,
            )
            context["billable_lessons"] = billable_lessons
            context["period_start"] = parsed_start
            context["period_end"] = parsed_end
            context["contract"] = contract

        return context

    def form_valid(self, form):
        period_start = form.cleaned_data["period_start"]
        period_end = form.cleaned_data["period_end"]
        contract = form.cleaned_data.get("contract")
        institute = form.cleaned_data.get("institute") or None

        try:
            invoice = InvoiceService.create_invoice_from_lessons(
                period_start,
                period_end,
                contract=contract,
                institute=institute,
                user=self.request.user,
            )
            lesson_count = invoice.items.count()
            messages.success(
                self.request,
                ngettext(
                    "Invoice {id} successfully created with {count} lesson.",
                    "Invoice {id} successfully created with {count} lessons.",
                    lesson_count,
                ).format(id=invoice.id, count=lesson_count),
            )
            return redirect("billing:invoice_detail", pk=invoice.pk)
        except ValueError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)


class InvoiceDeleteView(LoginRequiredMixin, DeleteView):
    """Löschen einer Rechnung."""

    model = Invoice
    template_name = "billing/invoice_confirm_delete.html"
    success_url = reverse_lazy("billing:invoice_list")

    def get_queryset(self):
        return _user_invoice_queryset(self.request.user)

    def delete(self, request, *args, **kwargs):
        """Löscht die Rechnung und setzt Lessons zurück."""
        invoice = self.get_object()
        reset_count = InvoiceService.delete_invoice(invoice)

        if reset_count > 0:
            messages.success(
                request,
                ngettext(
                    'Invoice deleted. {count} lesson was reset to "taught".',
                    'Invoice deleted. {count} lessons were reset to "taught".',
                    reset_count,
                ).format(count=reset_count),
            )
        else:
            messages.success(request, _("Invoice successfully deleted."))

        return redirect(self.success_url)


@login_required
def generate_invoice_document(request, pk):
    """Generiert das Rechnungsdokument für eine Invoice."""
    invoice = get_object_or_404(_user_invoice_queryset(request.user), pk=pk)

    try:
        InvoiceDocumentService.save_document(invoice)
        messages.success(request, _("Invoice document successfully generated."))
    except Exception as e:
        messages.error(request, _("Error generating document: {error}").format(error=str(e)))

    return redirect("billing:invoice_detail", pk=pk)


@login_required
def serve_invoice_document(request, pk):
    """Serviert das Rechnungsdokument für eine Invoice."""
    import os

    from django.http import FileResponse, Http404

    invoice = get_object_or_404(_user_invoice_queryset(request.user), pk=pk)

    if not invoice.document:
        raise Http404(_("Invoice document not found."))

    # Check if file exists
    file_path = invoice.document.path
    if not os.path.exists(file_path):
        raise Http404(_("Invoice document file not found."))

    # Serve the file
    return FileResponse(
        open(file_path, "rb"), content_type="text/html", filename=os.path.basename(file_path)
    )
