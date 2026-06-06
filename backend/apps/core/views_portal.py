"""
Tutor-seitige Portal-Views: Nachrichten-Thread pro Schüler.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from apps.portal.models import PortalMessage
from apps.contracts.models import Contract


class TutorMessageView(LoginRequiredMixin, TemplateView):
    """Nachrichten-Thread zwischen Tutor und Schüler (Portal)."""

    template_name = "core/tutor_messages.html"

    def get_student(self):
        return get_object_or_404(Contract, pk=self.kwargs["pk"], user=self.request.user)

    def get(self, request, *args, **kwargs):
        student = self.get_student()
        PortalMessage.objects.filter(contract=student, read_by_tutor=False).update(
            read_by_tutor=True
        )
        messages = PortalMessage.objects.filter(contract=student)
        unread_count = PortalMessage.objects.filter(contract=student, read_by_tutor=False).count()
        return self.render_to_response(
            {
                "student": student,
                "messages": messages,
                "unread_count": unread_count,
            }
        )

    def post(self, request, *args, **kwargs):
        student = self.get_student()
        text = request.POST.get("text", "").strip()
        if text:
            PortalMessage.objects.create(
                contract=student,
                sender_is_tutor=True,
                read_by_tutor=True,
                text=text,
            )
        return redirect("students:detail", pk=student.pk)
