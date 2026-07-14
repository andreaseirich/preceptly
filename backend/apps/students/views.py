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
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DeleteView, ListView

from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract
from apps.core.upload_validation import validate_file_magic
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
            from apps.contracts.models import Contract as _Contract
            from apps.core.feature_flags import FREE_STUDENT_LIMIT, is_new_free_user

            if is_new_free_user(request.user):
                student_count = _Contract.objects.filter(user=request.user).count()
                if student_count >= FREE_STUDENT_LIMIT:
                    messages.warning(
                        request,
                        format_html(
                            _(
                                "Free plan: the limit of 5 active students has been reached. "
                                'Your student was saved — <a href="{}">upgrade to a paid plan</a> for unlimited students.'
                            ),
                            reverse("core:landing") + "#pricing",
                        ),
                    )

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

        contract = self.get_object()

        with transaction.atomic():
            # Verknüpfte Portal-Accounts: löschen, wenn dies ihre einzige
            # Verknüpfung ist; sonst nur die Verknüpfung zu diesem Vertrag
            # entfernen (Account bleibt für andere Kinder erhalten).
            for plink in ParentStudentLink.objects.filter(contract=contract).select_related(
                "parent__user"
            ):
                portal_user = plink.parent
                if portal_user.tutor != self.request.user:
                    raise PermissionDenied
                only_link = (
                    not ParentStudentLink.objects.filter(parent=portal_user)
                    .exclude(contract=contract)
                    .exists()
                )
                if only_link:
                    django_user = portal_user.user
                    portal_user.delete()
                    django_user.delete()
                else:
                    plink.delete()

            messages.success(self.request, "Schüler erfolgreich gelöscht.")
            return super().form_valid(form)


class FamilyLinkView(LoginRequiredMixin, View):
    """Verknüpft zwei Verträge desselben Tutors zu einem gemeinsamen
    Portal-Familien-Konto (übergeordnete Mehrkind-Ansicht)."""

    def post(self, request, pk, other_pk):
        from apps.portal.models import ParentStudentLink

        contract_a = get_object_or_404(Contract, pk=pk, user=request.user)
        contract_b = get_object_or_404(Contract, pk=other_pk, user=request.user)

        link_a = ParentStudentLink.objects.filter(contract=contract_a).first()
        link_b = ParentStudentLink.objects.filter(contract=contract_b).first()

        if not link_a and not link_b:
            messages.error(
                request,
                "Bitte zuerst mindestens eines der beiden Kinder zum Portal einladen.",
            )
            return redirect("contracts:list")

        if link_a and link_b:
            if link_a.parent_id == link_b.parent_id:
                messages.info(request, "Diese beiden Kinder sind bereits verknüpft.")
                return redirect("contracts:list")
            # Beide haben schon einen eigenen Account: Account von A wird zum
            # Familien-Konto; der separate Account von B wird deaktiviert
            # (Nachrichtenhistorie bleibt erhalten, kein Löschen).
            account = link_a.parent
            other_django_user = link_b.parent.user
            link_b.is_active = False
            link_b.save(update_fields=["is_active"])
            if other_django_user.is_active:
                other_django_user.is_active = False
                other_django_user.save(update_fields=["is_active"])
            ParentStudentLink.objects.get_or_create(parent=account, contract=contract_b)
        else:
            existing_link = link_a or link_b
            missing_contract = contract_b if link_a else contract_a
            ParentStudentLink.objects.get_or_create(
                parent=existing_link.parent, contract=missing_contract
            )

        messages.success(
            request,
            f"{contract_a.full_name} und {contract_b.full_name} als Familie verknüpft.",
        )
        return redirect("contracts:list")


class PortalInviteView(LoginRequiredMixin, View):
    """Sendet eine Portal-Einladung für einen Vertrag.

    Eltern und Schüler teilen sich einen gemeinsamen Portal-Account pro
    Kind. Wird dieselbe E-Mail-Adresse für ein zweites Kind desselben
    Tutors eingeladen, wird der bestehende Account einfach mit dem
    weiteren Vertrag verknüpft (Familien-Zugang), statt einen neuen
    Account anzulegen.
    """

    def post(self, request, pk):
        from django.db import transaction

        from apps.portal.email_service import send_portal_invite

        contract = get_object_or_404(Contract, pk=pk, user=request.user)

        email = (
            request.POST.get("email", "").strip()
            or (contract.email or contract.parent_email or "").strip()
        )[:254]
        if not email or "\n" in email or "\r" in email:
            messages.error(request, "Ungültige E-Mail-Adresse.")
            return redirect("contracts:detail", pk=pk)
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Ungültige E-Mail-Adresse.")
            return redirect("contracts:detail", pk=pk)

        User = get_user_model()

        with transaction.atomic():
            # select_for_update verhindert Race Condition bei parallelen Requests
            existing_link = (
                ParentStudentLink.objects.select_for_update().filter(contract=contract).first()
            )
            if existing_link:
                messages.info(request, "Portal-Zugang bereits vorhanden.")
                return redirect("contracts:detail", pk=pk)

            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user and hasattr(existing_user, "portal_profile"):
                existing_portal = existing_user.portal_profile

                # Cross-Tenant-Schutz: generische Fehlermeldung, kein Info-Leak
                if existing_portal.tutor != request.user:
                    logger.warning(
                        "Portal invite cross-tenant attempt: tutor=%s email_hash=%s",
                        request.user.id,
                        hash(email.lower()),
                    )
                    messages.error(
                        request,
                        "Die Einladung konnte nicht erstellt werden. "
                        "Bitte kontaktieren Sie den Support, falls das Problem bestehen bleibt.",
                    )
                    return redirect("contracts:detail", pk=pk)

                # Familien-Zugang: bestehenden Account mit diesem Vertrag verknüpfen
                ParentStudentLink.objects.get_or_create(parent=existing_portal, contract=contract)
                messages.warning(
                    request,
                    "Hinweis: Diese E-Mail-Adresse hat bereits ein Portal-Konto — "
                    "als Familien-Zugang mit diesem Kind verknüpft.",
                )
                return redirect("contracts:detail", pk=pk)

            username = f"portal_{contract.pk}_{secrets.token_hex(4)}"
            portal_django_user = User.objects.create_user(
                username=username,
                email=email,
                password=secrets.token_hex(16),
            )
            portal_user = PortalUser.objects.create(
                user=portal_django_user, role="student", tutor=request.user
            )
            link = ParentStudentLink.objects.create(
                parent=portal_user,
                contract=contract,
                invite_token=secrets.token_urlsafe(32),
                invite_token_created_at=timezone.now(),
            )
            if not contract.parent_email and email != contract.email:
                contract.parent_email = email
                contract.save(update_fields=["parent_email"])

            try:
                send_portal_invite(contract, link, email, role="student")
                messages.success(request, f"Portal-Einladung gesendet an {email}.")
            except Exception:
                logger.exception("Portal invite email failed for contract_id=%s", contract.pk)
                messages.warning(request, "Could not send email. Please try again.")
                raise  # Rollback: kein verwaister Account ohne E-Mail-Versand

        return redirect("contracts:detail", pk=pk)


class PortalInviteResendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from apps.portal.email_service import send_portal_invite

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        link = get_object_or_404(ParentStudentLink, contract=contract)

        # H7 - Invite-Token nach erneutem Senden invalidieren und neu generieren
        link.invite_token = secrets.token_urlsafe(32)
        link.invite_token_created_at = timezone.now()
        link.is_active = False
        link.save(update_fields=["invite_token", "invite_token_created_at", "is_active"])

        # Email am Django-User auf aktuelle Contract-Email synchronisieren
        # (nicht nur wenn leer — auch wenn die Contract-Email nachträglich geändert wurde)
        django_user = link.parent.user
        if contract.email and contract.email.lower() != (django_user.email or "").lower():
            django_user.email = contract.email
            django_user.save(update_fields=["email"])
            logger.info(
                "Resend invite: E-Mail für User pk=%s aktualisiert auf %r",
                django_user.pk,
                contract.email,
            )

        recipient_email = django_user.email or contract.email
        if recipient_email:
            try:
                send_portal_invite(contract, link, recipient_email, role="student")
                messages.success(
                    request,
                    f"Einladung erneut gesendet an {recipient_email}.",
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

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        link = get_object_or_404(ParentStudentLink, contract=contract, is_active=True)

        tutor_name = request.user.get_full_name() or request.user.username
        recipient_email = link.parent.user.email or contract.email

        if recipient_email:
            try:
                send_login_reminder(contract, recipient_email, tutor_name, role="student")
                messages.success(
                    request,
                    f"Login-Erinnerung gesendet an {recipient_email}.",
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
            if not validate_file_magic(uploaded_file, ext):
                messages.error(
                    request,
                    "Dateityp nicht erlaubt (Inhalt stimmt nicht mit Dateiendung überein).",
                )
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
        if doc.file and doc.file.name:
            try:
                doc.file.delete(save=False)
            except Exception:
                logger.warning(
                    "Datei nicht löschbar (vermutlich nicht vorhanden): %s", doc.file.name
                )
        doc.delete()
        messages.success(request, "Dokument gelöscht.")
        return redirect("students:documents", pk=pk)


class StudentDocumentDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk, doc_pk):
        from apps.students.models import StudentDocument

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        doc = get_object_or_404(StudentDocument, pk=doc_pk, student=contract)
        if not doc.file or not doc.file_exists:
            raise Http404
        filename = doc.display_name or os.path.basename(doc.file.name)
        return FileResponse(doc.file.open("rb"), as_attachment=True, filename=filename)
