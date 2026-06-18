"""
Views for student management (now backed by Contract model).
"""

import logging
import os
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract
from apps.portal.models import ParentStudentLink, PortalUser, ProgressNote
from apps.students.booking_code_service import set_booking_code

logger = logging.getLogger(__name__)


class StudentListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = "students/student_list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        return Contract.objects.filter(user=self.request.user)


class StudentDetailView(LoginRequiredMixin, DetailView):
    model = Contract
    template_name = "students/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        return Contract.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        from apps.portal.models import PortalMessage, StudentPortalLink

        context = super().get_context_data(**kwargs)
        student = self.object  # Contract object
        context["portal_link"] = StudentPortalLink.objects.filter(contract=student).first()
        context["parent_links"] = ParentStudentLink.objects.filter(contract=student).select_related(
            "parent"
        )
        context["progress_notes"] = ProgressNote.objects.filter(contract=student).order_by(
            "-created_at"
        )[:10]
        context["unread_messages"] = PortalMessage.objects.filter(
            contract=student, read_by_tutor=False
        ).count()
        portal_link = context.get("portal_link")
        if portal_link:
            site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
            context["student_activation_url"] = (
                f"{site_url}/portal/activate/{portal_link.invite_token}/"
            )
        return context


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
            return redirect("students:detail", pk=contract.pk)
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
            return redirect("students:detail", pk=contract.pk)
        return render(request, "students/student_form.html", {"form": form, "object": contract})


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    model = Contract
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("students:list")

    def get_queryset(self):
        return Contract.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        from apps.portal.models import StudentPortalLink

        contract = self.get_object()

        # Student portal account
        spl = StudentPortalLink.objects.filter(contract=contract).first()
        if spl:
            portal_user = spl.portal_user
            if portal_user.tutor != request.user:
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
                if parent_portal.tutor != request.user:
                    raise PermissionDenied
                django_user = parent_portal.user
                parent_portal.delete()
                django_user.delete()

        messages.success(request, "Schüler erfolgreich gelöscht.")
        return super().delete(request, *args, **kwargs)


class PortalInviteCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from apps.portal.email_service import send_portal_invite
        from apps.portal.models import StudentPortalLink

        contract = get_object_or_404(Contract, pk=pk, user=request.user)

        if not StudentPortalLink.objects.filter(contract=contract).exists():
            User = get_user_model()
            username = f"portal_student_{contract.pk}_{secrets.token_hex(4)}"
            portal_django_user = User.objects.create_user(
                username=username, password=secrets.token_hex(16)
            )
            portal_user = PortalUser.objects.create(
                user=portal_django_user, role="student", tutor=request.user
            )
            spl = StudentPortalLink.objects.create(
                portal_user=portal_user,
                contract=contract,
                invite_token=secrets.token_urlsafe(32),
            )
            if contract.email:
                try:
                    send_portal_invite(contract, spl, contract.email, role="student")
                    messages.success(
                        request,
                        f"Portal-Einladung gesendet an {contract.email}.",
                    )
                except Exception as exc:
                    logger.error("Portal invite email failed: %s", exc)
                    messages.warning(
                        request,
                        "Could not send email. Please try again.",
                    )
            else:
                messages.info(
                    request,
                    "Portal-Account erstellt. Kein E-Mail-Versand möglich.",
                )
        else:
            messages.info(request, "Portal-Zugang bereits vorhanden.")

        return redirect("students:detail", pk=pk)


class PortalInviteParentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from apps.portal.email_service import send_portal_invite

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        parent_email = request.POST.get("parent_email", "").strip()
        if not parent_email:
            return redirect("students:detail", pk=pk)

        User = get_user_model()
        existing_user = User.objects.filter(email__iexact=parent_email).first()
        if existing_user and hasattr(existing_user, "portal_profile"):
            existing_portal = existing_user.portal_profile
            existing_link = ParentStudentLink.objects.filter(
                parent=existing_portal, contract=contract
            ).first()
            if existing_link:
                messages.info(
                    request,
                    f"Dieses Konto ({parent_email}) ist bereits als Elternteil verknüpft.",
                )
            else:
                ParentStudentLink.objects.get_or_create(parent=existing_portal, contract=contract)
                messages.warning(
                    request,
                    f"Hinweis: {parent_email} hat bereits ein Portal-Konto.",
                )
            return redirect("students:detail", pk=pk)

        username = f"parent_{contract.pk}_{secrets.token_hex(4)}"
        password_temp = secrets.token_hex(8)
        user = User.objects.create_user(
            username=username, email=parent_email, password=password_temp
        )
        portal_user = PortalUser.objects.create(user=user, role="parent", tutor=request.user)
        parent_link, _ = ParentStudentLink.objects.get_or_create(
            parent=portal_user, contract=contract
        )
        try:
            send_portal_invite(contract, parent_link, parent_email, role="parent")
            messages.success(
                request,
                f"Eltern-Einladung gesendet an {parent_email}.",
            )
        except Exception as exc:
            logger.error("Parent invite email failed: %s", exc)
            messages.warning(
                request,
                "Could not send email. Please try again.",
            )
        return redirect("students:detail", pk=pk)


class PortalInviteResendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from apps.portal.email_service import send_portal_invite
        from apps.portal.models import StudentPortalLink

        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        spl = get_object_or_404(StudentPortalLink, contract=contract)
        if contract.email:
            try:
                send_portal_invite(contract, spl, contract.email, role="student")
                messages.success(
                    request,
                    f"Einladung erneut gesendet an {contract.email}.",
                )
            except Exception as exc:
                logger.error("Portal resend email failed: %s", exc)
                messages.warning(
                    request,
                    "Could not send email. Please try again.",
                )
        else:
            messages.info(request, "Kein E-Mail-Versand möglich.")
        return redirect("students:detail", pk=pk)


class ProgressNoteCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk, user=request.user)
        text = request.POST.get("text", "").strip()
        if text:
            ProgressNote.objects.create(contract=contract, tutor=request.user, text=text)
        return redirect("students:detail", pk=pk)


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
        docs = StudentDocument.objects.filter(student=contract)
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
            max_size = 10 * 1024 * 1024  # 10 MB
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext not in allowed_extensions:
                messages.error(request, "Dateityp nicht erlaubt.")
                return redirect(request.path)
            if uploaded_file.size > max_size:
                messages.error(request, "Datei ist zu groß (max. 10 MB).")
                return redirect(request.path)
        if not uploaded_file:
            messages.warning(request, "Keine Datei ausgewählt.")
            return redirect("students:documents", pk=pk)
        name = request.POST.get("name", "").strip()
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
        doc.delete()
        messages.success(request, "Datei gelöscht.")
        return redirect("students:documents", pk=pk)
