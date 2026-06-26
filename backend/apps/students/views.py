"""
Views for student management (now backed by Contract model).
"""

import logging
import os
import re
import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DeleteView, ListView

from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract
from apps.portal.models import ParentStudentLink, PortalUser, ProgressNote
from apps.students.booking_code_service import set_booking_code

logger = logging.getLogger(__name__)
_MAX_DOC_NAME_LEN = 200
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\-\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df ]")


class StudentListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = "students/student_list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        return Contract.objects.filter(user=self.request.user)


class StudentCreateView(LoginRequiredMixin, View):
    """Create new student = create new contract with student fields."""

    def get(self, request):
        form = ContractForm(user=request.user)
        return render(request, "students/student_form.html", {"form": form, "is_create": True})

    def post(self, request):
        form = ContractForm(request.POST, user=request.user)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.user = request.user
            contract.save()
            messages.success(request, _("Student successfully created."))
            return redirect("contracts:detail", pk=contract.pk)
        return render(request, "students/student_form.html", {"form": form, "is_create": True})


class StudentUpdateView(LoginRequiredMixin, View):
    """Update student info (= update contract)."""

    def get_object(self, request, pk):
        return get_object_or_404(Contract, pk=pk, user=request.user)

    def get(self, request, pk):
        contract = self.get_object(request, pk)
        form = ContractForm(instance=contract, user=request.user)
        return render(request, "students/student_form.html", {"form": form, "object": contract})

    def post(self, request, pk):
        contract = self.get_object(request, pk)
        form = ContractForm(request.POST, instance=contract, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Student successfully updated."))
            return redirect("contracts:detail", pk=contract.pk)
        return render(request, "students/student_form.html", {"form": form, "object": contract})


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    model = Contract
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("students:list")

    def get_queryset(self):
        return Contract.objects.filter(user=self.request.user)

    def form_valid(self, form):
        from django.db import transaction

        from apps.portal.models import StudentPortalLink

        contract = self.get_object()

        with transaction.atomic():
            # Student portal account
            spl = StudentPortalLink.objects.filter(contract=contract).first()
            if spl:
                portal_user = spl.portal_user
                if portal_user.tutor != self.request.user:
                    raise PermissionDenied
                django_user = portal_user.user
                portal_user.delete()
                django_user.delete()

            # Parent portal accounts (only if no other children)
            for plink in ParentStudentLink.objects.filter(contract=contract).select_related(
                "parent__user"
            ):
                parent_portal = plink.parent
                if (
                    not ParentStudentLink.objects.filter(parent=parent_portal)
                    .exclude(contract=contract)
                    .exists()
                ):
                    if parent_portal.tutor != self.request.user:
                        raise PermissionDenied
                    django_user = parent_portal.user
                    parent_portal.delete()
                    django_user.delete()

            messages.success(self.request, "Schüler erfolgreich gelöscht.")
            return super().form_valid(form)


class PortalInviteCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from django.db import transaction

        from apps.portal.email_service import send_portal_invite
        from apps.portal.models import StudentPortalLink

        contract = get_object_or_404(Contract, pk=pk, user=request.user)

        with transaction.atomic():
            # select_for_update verhindert Race Condition bei parallelen Requests
            existing = (
                StudentPortalLink.objects.select_for_update().filter(contract=contract).first()
            )
            if existing:
                messages.info(request, "Portal-Zugang bereits vorhanden.")
                return redirect("contracts:detail", pk=pk)

            User = get_user_model()
            username = f"portal_student_{contract.pk}_{secrets.token_hex(4)}"
            portal_django_user = User.objects.create_user(
                username=username,
                email=contract.email or "",
                password=secrets.token_hex(16),
            )
            portal_user = PortalUser.objects.create(
                user=portal_django_user, role="student", tutor=request.user
            )
            spl = StudentPortalLink.objects.create(
                portal_user=portal_user,
                contract=contract,
                invite_token=secrets.token_urlsafe(32),
                invite_token_created_at=timezone.now(),
            )

            if contract.email:
                try:
                    send_portal_invite(contract, spl, contract.email, role="student")
                    messages.success(
                        request,
                        f"Portal-Einladung gesendet an {contract.email}.",
                    )
                except Exception:
                    logger.exception("Portal invite email failed for contract_id=%s", contract.pk)
                    messages.warning(
                        request,
                        "Could not send email. Please try again.",
                    )
                    raise  # Rollback: kein verwaister Account ohne E-Mail-Versand
            else:
                messages.info(
                    request,
                    "Portal-Account erstellt. Kein E-Mail-Versand möglich.",
                )

        return redirect("contracts:detail", pk=pk)


class PortalInviteParentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from django.db import transaction

        from apps.portal.email_service import send_portal_invite

        contract = get_object_or_404(Contract, pk=pk, user=request.user)

        # E-Mail-Validierung: Längenbegrenzung + CRLF-Filter + Format-Prüfung
        parent_email = request.POST.get("parent_email", "").strip()[:254]
        if not parent_email or "\n" in parent_email or "\r" in parent_email:
            messages.error(request, "Ungültige E-Mail-Adresse.")
            return redirect("contracts:detail", pk=pk)
        try:
            validate_email(parent_email)
        except ValidationError:
            messages.error(request, "Ungültige E-Mail-Adresse.")
            return redirect("contracts:detail", pk=pk)

        User = get_user_model()
        existing_user = User.objects.filter(email__iexact=parent_email).first()
        if existing_user and hasattr(existing_user, "portal_profile"):
            existing_portal = existing_user.portal_profile

            # Cross-Tenant-Schutz: generische Fehlermeldung, kein Info-Leak
            if existing_portal.tutor != request.user:
                logger.warning(
                    "Parent invite cross-tenant attempt: tutor=%s email_hash=%s",
                    request.user.id,
                    hash(parent_email.lower()),
                )
                messages.error(
                    request,
                    "Die Einladung konnte nicht erstellt werden. "
                    "Bitte kontaktieren Sie den Support, falls das Problem bestehen bleibt.",
                )
                return redirect("contracts:detail", pk=pk)

            existing_link = ParentStudentLink.objects.filter(
                parent=existing_portal, contract=contract
            ).first()
            if existing_link:
                messages.info(
                    request,
                    "Dieses Konto ist bereits als Elternteil verknüpft.",
                )
            else:
                ParentStudentLink.objects.get_or_create(parent=existing_portal, contract=contract)
                messages.warning(
                    request,
                    "Hinweis: Diese E-Mail-Adresse hat bereits ein Portal-Konto.",
                )
            return redirect("contracts:detail", pk=pk)

        with transaction.atomic():
            username = f"parent_{contract.pk}_{secrets.token_hex(4)}"
            user = User.objects.create_user(username=username, email=parent_email)
            user.set_unusable_password()
            user.save()
            portal_user = PortalUser.objects.create(user=user, role="parent", tutor=request.user)
            parent_link, _ = ParentStudentLink.objects.get_or_create(
                parent=portal_user, contract=contract
            )
            try:
                send_portal_invite(contract, parent_link, parent_email, role="parent")
                messages.success(
                    request,
                    "Eltern-Einladung wurde gesendet.",
                )
            except Exception:
                logger.exception("Parent invite email failed for contract_id=%s", contract.pk)
                messages.warning(
                    request,
                    "Could not send email. Please try again.",
                )
                raise  # Rollback: kein verwaister Account ohne E-Mail-Versand

        return redirect("contracts:detail", pk=pk)


class PortalInviteResendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from apps.portal.email_service import send_portal_invite
        from apps.portal.models import StudentPortalLink

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        spl = get_object_or_404(StudentPortalLink, contract=contract)

        # H7 - Invite-Token nach erneutem Senden invalidieren und neu generieren
        spl.invite_token = secrets.token_urlsafe(32)
        spl.invite_token_created_at = timezone.now()
        spl.is_active = False
        spl.save(update_fields=["invite_token", "invite_token_created_at", "is_active"])

        # Email am Django-User sicherstellen (Backfill für Accounts ohne Email)
        django_user = spl.portal_user.user
        if contract.email and not django_user.email:
            django_user.email = contract.email
            django_user.save(update_fields=["email"])

        if contract.email:
            try:
                send_portal_invite(contract, spl, contract.email, role="student")
                messages.success(
                    request,
                    f"Einladung erneut gesendet an {contract.email}.",
                )
            except Exception:
                logger.exception("Portal resend email failed for contract_id=%s", contract.pk)
                messages.warning(
                    request,
                    "Could not send email. Please try again.",
                )
        else:
            messages.info(request, "Kein E-Mail-Versand möglich.")
        return redirect("contracts:detail", pk=pk)


class PortalLoginReminderView(LoginRequiredMixin, View):
    """Login-Erinnerung an bereits aktive Portal-Nutzer senden."""

    def post(self, request, pk):
        from apps.portal.email_service import send_login_reminder
        from apps.portal.models import StudentPortalLink

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        get_object_or_404(StudentPortalLink, contract=contract, is_active=True)

        tutor_name = request.user.get_full_name() or request.user.username

        if contract.email:
            try:
                send_login_reminder(contract, contract.email, tutor_name, role="student")
                messages.success(
                    request,
                    f"Login-Erinnerung gesendet an {contract.email}.",
                )
            except Exception:
                logger.exception("Portal login reminder failed for contract_id=%s", contract.pk)
                messages.warning(
                    request, "E-Mail konnte nicht gesendet werden. Bitte erneut versuchen."
                )
        else:
            messages.info(request, "Kein E-Mail-Versand möglich — keine E-Mail-Adresse hinterlegt.")
        return redirect("contracts:detail", pk=pk)


class ProgressNoteCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        text = request.POST.get("text", "").strip()
        if text:
            ProgressNote.objects.create(contract=contract, tutor=request.user, text=text)
        return redirect("contracts:detail", pk=pk)


class StudentRegenerateBookingCodeView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            contract = Contract.objects.get(pk=pk, user=request.user)
        except Contract.DoesNotExist:
            return JsonResponse({"success": False, "message": _("Student not found.")}, status=404)
        new_code = set_booking_code(contract)
        return JsonResponse({"success": True, "booking_code": new_code})


class StudentDocumentListView(LoginRequiredMixin, View):
    def get(self, request, pk):
        from apps.students.models import StudentDocument

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        docs = StudentDocument.objects.filter(student=contract, student__user=request.user)
        return render(
            request, "students/student_documents.html", {"student": contract, "documents": docs}
        )

    def post(self, request, pk):
        from apps.students.models import StudentDocument

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        uploaded_file = request.FILES.get("file")
        if uploaded_file:
            allowed_extensions = {
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".docx",
                ".doc",
                ".xlsx",
                ".xls",
                ".txt",
            }
            max_size = 50 * 1024 * 1024  # 50 MB
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext not in allowed_extensions:
                messages.error(request, "Dateityp nicht erlaubt.")
                return redirect(request.path)
            if uploaded_file.size > max_size:
                messages.error(request, "Datei ist zu groß (max. 50 MB).")
                return redirect(request.path)
        if not uploaded_file:
            messages.warning(request, "Keine Datei ausgewählt.")
            return redirect("students:documents", pk=pk)

        # Name-Sanitisierung: Längenbegrenzung + nur erlaubte Zeichen
        name = request.POST.get("name", "").strip()[:_MAX_DOC_NAME_LEN]
        name = _SAFE_NAME_RE.sub("", name)

        StudentDocument.objects.create(
            student=contract, file=uploaded_file, name=name, uploaded_by_tutor=True
        )
        messages.success(request, "Datei hochgeladen.")
        return redirect("students:documents", pk=pk)


class StudentDocumentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, doc_pk):
        from apps.students.models import StudentDocument

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        doc = get_object_or_404(StudentDocument, pk=doc_pk, student=contract)
        if doc.file:
            doc.file.delete(save=False)
        doc.delete()
        messages.success(request, "Dokument gelöscht.")
        return redirect("students:documents", pk=pk)
