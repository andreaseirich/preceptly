"""
Views for student CRUD operations.
"""

import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.portal.models import ParentStudentLink, PortalUser, ProgressNote
from apps.students.booking_code_service import set_booking_code
from apps.students.forms import StudentForm
from apps.students.models import Student


class StudentListView(LoginRequiredMixin, ListView):
    """List of all students for the current user."""

    model = Student
    template_name = "students/student_list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class StudentDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a student."""

    model = Student
    template_name = "students/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        from apps.portal.models import (
            ParentStudentLink,
            PortalMessage,
            ProgressNote,
            StudentPortalLink,
        )

        context = super().get_context_data(**kwargs)
        student = self.object
        context["portal_link"] = StudentPortalLink.objects.filter(student=student).first()
        context["parent_links"] = ParentStudentLink.objects.filter(student=student).select_related(
            "parent"
        )
        context["progress_notes"] = ProgressNote.objects.filter(student=student).order_by(
            "-created_at"
        )[:10]
        context["unread_messages"] = PortalMessage.objects.filter(
            student=student, read_by_tutor=False
        ).count()
        portal_link = context.get("portal_link")
        if portal_link:
            site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
            context["student_activation_url"] = (
                f"{site_url}/portal/activate/{portal_link.invite_token}/"
            )
        return context


class StudentCreateView(LoginRequiredMixin, CreateView):
    """Create a new student."""

    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, _("Student successfully created."))
        return super().form_valid(form)


class StudentUpdateView(LoginRequiredMixin, UpdateView):
    """Update a student."""

    model = Student
    form_class = StudentForm
    template_name = "students/student_form.html"
    success_url = reverse_lazy("students:list")

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Student successfully updated."))
        return super().form_valid(form)


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a student."""

    model = Student
    template_name = "students/student_confirm_delete.html"
    success_url = reverse_lazy("students:list")

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Student successfully deleted."))
        return super().delete(request, *args, **kwargs)


class PortalInviteCreateView(LoginRequiredMixin, View):
    """Erstellt PortalUser + StudentPortalLink und generiert Invite-Token."""

    def post(self, request, pk):
        from apps.portal.models import PortalUser, StudentPortalLink

        student = get_object_or_404(Student, pk=pk, user=request.user)

        if not StudentPortalLink.objects.filter(student=student).exists():
            User = get_user_model()
            username = f"portal_student_{student.pk}_{uuid.uuid4().hex[:8]}"
            portal_django_user = User.objects.create_user(
                username=username,
                password=uuid.uuid4().hex,
            )
            portal_user = PortalUser.objects.create(
                user=portal_django_user,
                role="student",
                tutor=request.user,
            )
            StudentPortalLink.objects.create(
                portal_user=portal_user,
                student=student,
                invite_token=uuid.uuid4().hex,
            )
            from apps.portal.email_service import send_portal_invite

            spl = StudentPortalLink.objects.get(portal_user=portal_user)
            site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
            activation_url = f"{site_url}/portal/activate/{spl.invite_token}/"
            if student.email:
                try:
                    send_portal_invite(student, spl, student.email, role="student")
                    messages.success(
                        request,
                        f"Portal-Einladung gesendet an {student.email}. "
                        f"Aktivierungslink: {activation_url}",
                    )
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).error("Portal invite email failed: %s", exc)
                    messages.warning(
                        request,
                        f"Portal-Account erstellt, aber E-Mail-Versand fehlgeschlagen: {exc}. "
                        f"Aktivierungslink zum manuellen Teilen: {activation_url}",
                    )
            else:
                messages.info(
                    request,
                    f"Portal-Account erstellt. Schüler hat keine E-Mail-Adresse. "
                    f"Aktivierungslink zum manuellen Teilen: {activation_url}",
                )
        else:
            spl = StudentPortalLink.objects.get(student=student)
            site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
            activation_url = f"{site_url}/portal/activate/{spl.invite_token}/"
            messages.info(
                request, f"Portal-Zugang bereits vorhanden. Aktivierungslink: {activation_url}"
            )

        return redirect("students:detail", pk=pk)


class PortalInviteParentView(LoginRequiredMixin, View):
    """Create a parent portal account and link to student."""

    def post(self, request, pk):
        import secrets as _secrets

        student = get_object_or_404(Student, pk=pk, user=request.user)
        parent_email = request.POST.get("parent_email", "").strip()
        if not parent_email:
            return redirect("students:detail", pk=pk)

        # Kollisions-Check: E-Mail bereits in einem Portal-Konto?
        User = get_user_model()
        site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
        existing_user = User.objects.filter(email__iexact=parent_email).first()
        if existing_user and hasattr(existing_user, "portal_profile"):
            existing_portal = existing_user.portal_profile
            # Prüfen ob bereits eine Eltern-Verknüpfung für diesen Schüler existiert
            existing_link = ParentStudentLink.objects.filter(
                parent=existing_portal, student=student
            ).first()
            if existing_link:
                activation_url = f"{site_url}/portal/activate/{existing_link.invite_token}/"
                messages.info(
                    request,
                    f"Dieses Konto ({parent_email}) ist bereits als Elternteil verknüpft. "
                    f"Aktivierungslink: {activation_url}",
                )
            else:
                # Bestehendes Portal-Konto als Elternteil verknüpfen (kein Duplikat)
                parent_link, _ = ParentStudentLink.objects.get_or_create(
                    parent=existing_portal, student=student
                )
                activation_url = f"{site_url}/portal/activate/{parent_link.invite_token}/"
                messages.warning(
                    request,
                    f"Hinweis: {parent_email} hat bereits ein Portal-Konto. "
                    f"Es wurde kein neues Konto erstellt – das bestehende Konto wurde verknüpft. "
                    f"Aktivierungslink: {activation_url}",
                )
            return redirect("students:detail", pk=pk)

        username = f"parent_{student.pk}_{_secrets.token_hex(4)}"
        password_temp = _secrets.token_hex(8)
        user = User.objects.create_user(
            username=username, email=parent_email, password=password_temp
        )
        portal_user = PortalUser.objects.create(user=user, role="parent", tutor=request.user)
        parent_link, _ = ParentStudentLink.objects.get_or_create(
            parent=portal_user, student=student
        )
        from apps.portal.email_service import send_portal_invite

        site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
        activation_url = f"{site_url}/portal/activate/{parent_link.invite_token}/"
        try:
            send_portal_invite(student, parent_link, parent_email, role="parent")
            messages.success(
                request,
                f"Eltern-Einladung gesendet an {parent_email}. Aktivierungslink: {activation_url}",
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error("Parent invite email failed: %s", exc)
            messages.warning(
                request,
                f"Eltern-Account erstellt, aber E-Mail-Versand fehlgeschlagen: {exc}. "
                f"Aktivierungslink zum manuellen Teilen: {activation_url}",
            )
        return redirect("students:detail", pk=pk)


class PortalInviteResendView(LoginRequiredMixin, View):
    """Sendet die Portal-Einladungs-E-Mail erneut."""

    def post(self, request, pk):
        from apps.portal.email_service import send_portal_invite
        from apps.portal.models import StudentPortalLink

        student = get_object_or_404(Student, pk=pk, user=request.user)
        spl = get_object_or_404(StudentPortalLink, student=student)
        site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
        activation_url = f"{site_url}/portal/activate/{spl.invite_token}/"
        if student.email:
            try:
                send_portal_invite(student, spl, student.email, role="student")
                messages.success(
                    request,
                    f"Einladung erneut gesendet an {student.email}. "
                    f"Aktivierungslink: {activation_url}",
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).error("Portal resend email failed: %s", exc)
                messages.warning(
                    request,
                    f"E-Mail-Versand fehlgeschlagen: {exc}. "
                    f"Aktivierungslink zum manuellen Teilen: {activation_url}",
                )
        else:
            messages.info(
                request,
                f"Kein E-Mail-Versand möglich: Schüler hat keine E-Mail-Adresse. "
                f"Aktivierungslink: {activation_url}",
            )
        return redirect("students:detail", pk=pk)


class ProgressNoteCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        student = get_object_or_404(Student, pk=pk, user=request.user)
        text = request.POST.get("text", "").strip()
        if text:
            ProgressNote.objects.create(student=student, tutor=request.user, text=text)
        return redirect("students:detail", pk=pk)


class StudentRegenerateBookingCodeView(LoginRequiredMixin, View):
    """Regenerate booking code for a student. Returns new code once (never stored)."""

    def post(self, request, pk):
        try:
            student = Student.objects.get(pk=pk, user=request.user)
        except Student.DoesNotExist:
            return JsonResponse({"success": False, "message": _("Student not found.")}, status=404)

        new_code = set_booking_code(student)
        return JsonResponse({"success": True, "booking_code": new_code})


class StudentDocumentListView(LoginRequiredMixin, View):
    """Dokumente eines Schülers – Tutor-Seite."""

    def get(self, request, pk):
        from apps.students.models import StudentDocument

        student = get_object_or_404(Student, pk=pk, user=request.user)
        docs = StudentDocument.objects.filter(student=student)
        return render(
            request,
            "students/student_documents.html",
            {
                "student": student,
                "documents": docs,
            },
        )

    def post(self, request, pk):
        from apps.students.models import StudentDocument

        student = get_object_or_404(Student, pk=pk, user=request.user)
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.warning(request, "Keine Datei ausgewählt.")
            return redirect("students:documents", pk=pk)
        name = request.POST.get("name", "").strip()
        StudentDocument.objects.create(
            student=student,
            file=uploaded_file,
            name=name,
            uploaded_by_tutor=True,
        )
        messages.success(request, "Datei hochgeladen.")
        return redirect("students:documents", pk=pk)


class StudentDocumentDeleteView(LoginRequiredMixin, View):
    """Dokument löschen – Tutor-Seite."""

    def post(self, request, pk, doc_pk):
        from apps.students.models import StudentDocument

        student = get_object_or_404(Student, pk=pk, user=request.user)
        doc = get_object_or_404(StudentDocument, pk=doc_pk, student=student)
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, "Dokument gelöscht.")
        return redirect("students:documents", pk=pk)
