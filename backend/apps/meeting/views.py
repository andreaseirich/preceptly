"""
Views für Meeting-Räume (Tutor + Portal-Nutzer).
"""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.lessons.models import Session
from apps.meeting.models import MeetingRoom
from apps.portal.models import ParentStudentLink, StudentPortalLink
from apps.portal.views import get_portal_user

logger = logging.getLogger(__name__)


def _get_meeting_room(lesson: Session) -> MeetingRoom:
    """Gibt den MeetingRoom zurück oder erstellt ihn."""
    room, _ = MeetingRoom.objects.get_or_create(lesson=lesson)
    return room


class StartMeetingView(LoginRequiredMixin, View):
    """Tutor startet/betritt ein Meeting für eine bestimmte Stunde."""

    def get(self, request, lesson_pk):
        lesson = get_object_or_404(Session, pk=lesson_pk, contract__user=request.user)
        room = _get_meeting_room(lesson)
        return redirect("meeting:room", token=room.token)

    def post(self, request, lesson_pk):
        return self.get(request, lesson_pk)


class MeetingRoomView(View):
    """
    Der eigentliche Meeting-Raum.
    Zugang: Tutor (eingeloggt, Stunde gehört ihm) ODER Portal-Nutzer (Schüler/Elternteil).
    """

    template_name = "meeting/room.html"

    def get(self, request, token):
        room = get_object_or_404(MeetingRoom, token=token, is_active=True)
        lesson = room.lesson

        # Check tutor access
        if (
            request.user.is_authenticated
            and hasattr(lesson, "contract")
            and lesson.contract.user == request.user
        ):
            display_name = f"{request.user.get_full_name() or request.user.username} (Tutor)"
            documents = lesson.documents.all()
            return render(
                request,
                self.template_name,
                {
                    "room": room,
                    "lesson": lesson,
                    "display_name": display_name,
                    "documents": documents,
                    "is_tutor": True,
                },
            )

        # Check portal user access
        portal_user = get_portal_user(request)
        if portal_user:
            if portal_user.role == "student":
                link = StudentPortalLink.objects.filter(
                    portal_user=portal_user, is_active=True, contract=lesson.contract
                ).first()
                if not link:
                    return HttpResponseForbidden("Kein Zugriff auf dieses Meeting.")
                display_name = lesson.contract.full_name
            elif portal_user.role == "parent":
                has_access = ParentStudentLink.objects.filter(
                    parent=portal_user, contract=lesson.contract
                ).exists()
                if not has_access:
                    return HttpResponseForbidden("Kein Zugriff auf dieses Meeting.")
                display_name = (
                    f"{portal_user.user.get_full_name() or portal_user.user.username} (Elternteil)"
                )
            else:
                return HttpResponseForbidden()

            documents = lesson.documents.all()
            return render(
                request,
                self.template_name,
                {
                    "room": room,
                    "lesson": lesson,
                    "display_name": display_name,
                    "documents": documents,
                    "is_tutor": False,
                },
            )

        # Not authenticated at all — redirect to portal login
        return redirect("portal:login")
