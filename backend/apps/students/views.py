"""
Views for student CRUD operations.
"""

import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
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
            # Send invitation email if student has email
            from apps.portal.email_service import send_portal_invite

            if student.email:
                spl = StudentPortalLink.objects.get(portal_user=portal_user)
                try:
                    send_portal_invite(student, spl, student.email, role="student")
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).error("Portal invite email failed: %s", exc)

        return redirect("students:detail", pk=pk)


class PortalInviteParentView(LoginRequiredMixin, View):
    """Create a parent portal account and link to student."""

    def post(self, request, pk):
        import secrets as _secrets

        student = get_object_or_404(Student, pk=pk, user=request.user)
        parent_email = request.POST.get("parent_email", "").strip()
        if not parent_email:
            return redirect("students:detail", pk=pk)
        User = get_user_model()
        username = f"parent_{student.pk}_{_secrets.token_hex(4)}"
        password_temp = _secrets.token_hex(8)
        user = User.objects.create_user(username=username, password=password_temp)
        portal_user = PortalUser.objects.create(user=user, role="parent", tutor=request.user)
        parent_link, _ = ParentStudentLink.objects.get_or_create(
            parent=portal_user, student=student
        )
        from apps.portal.email_service import send_portal_invite

        try:
            send_portal_invite(student, parent_link, parent_email, role="parent")
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error("Parent invite email failed: %s", exc)
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
