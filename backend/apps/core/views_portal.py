"""
Tutor-seitige Portal-Views: Nachrichten-Thread pro Schüler.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from apps.contracts.models import Contract
from apps.portal.models import ParentStudentLink, PortalMessage, StudentPortalLink


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
        chat_messages = PortalMessage.objects.filter(contract=student)
        unread_count = PortalMessage.objects.filter(contract=student, read_by_tutor=False).count()
        return self.render_to_response(
            {
                "student": student,
                "chat_messages": chat_messages,
                "unread_count": unread_count,
            }
        )

    def post(self, request, *args, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            student = self.get_student()
            text = request.POST.get("body", "").strip()[:5000]
            if text:
                PortalMessage.objects.create(
                    contract=student,
                    sender_is_tutor=True,
                    read_by_tutor=True,
                    text=text,
                )
        return redirect("core:tutor_messages", pk=student.pk)


class TutorMessagesOverviewView(LoginRequiredMixin, TemplateView):
    """Übersicht aller Chat-Threads des Tutors (Schüler + Eltern im Portal)."""

    template_name = "core/tutor_messages_overview.html"

    def get(self, request, *args, **kwargs):
        from apps.contracts.models import Contract

        student_contract_ids = set(
            StudentPortalLink.objects.filter(
                portal_user__tutor=request.user, is_active=True
            ).values_list("contract_id", flat=True)
        )
        parent_contract_ids = set(
            ParentStudentLink.objects.filter(parent__tutor=request.user).values_list(
                "contract_id", flat=True
            )
        )
        all_ids = student_contract_ids | parent_contract_ids

        threads = []
        for contract in Contract.objects.filter(pk__in=all_ids, user=request.user):
            unread = PortalMessage.objects.filter(contract=contract, read_by_tutor=False).count()
            last_msg = (
                PortalMessage.objects.filter(contract=contract).order_by("-created_at").first()
            )
            threads.append(
                {
                    "contract": contract,
                    "unread": unread,
                    "last_msg": last_msg,
                }
            )

        threads.sort(
            key=lambda t: (
                0 if t["unread"] else 1,
                -(t["last_msg"].created_at.timestamp() if t["last_msg"] else 0),
            )
        )

        return self.render_to_response({"threads": threads})
