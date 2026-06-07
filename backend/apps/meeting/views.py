"""
Views für Meeting-Räume (Tutor + Portal-Nutzer).
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
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

    Portal-Nutzer werden ZUERST geprüft, damit in Testsituationen (selber Browser,
    Tutor + Portal gleichzeitig eingeloggt) Portal-Nutzer nicht als Tutor einsteigen.
    """

    template_name = "meeting/room.html"

    def get(self, request, token):
        room = get_object_or_404(MeetingRoom, token=token, is_active=True)
        lesson = room.lesson
        turn_servers = getattr(settings, "MEETING_ICE_SERVERS", [])

        # ── 1. Portal-Nutzer zuerst prüfen ────────────────────────────────────
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
                    portal_user.user.get_full_name() or portal_user.user.username
                ) + " (Elternteil)"
            else:
                return HttpResponseForbidden()

            # Zurück-URL rollenabhängig
            if portal_user.role == "student":
                back_url = f"/portal/student/lessons/{lesson.pk}/"
            else:
                back_url = "/portal/parent/"

            return render(
                request,
                self.template_name,
                {
                    "room": room,
                    "lesson": lesson,
                    "display_name": display_name,
                    "documents": lesson.documents.all(),
                    "is_tutor": False,
                    "back_url": back_url,
                    "MEETING_TURN_SERVERS": turn_servers,
                },
            )

        # ── 2. Tutor-Zugang (Django-Auth) ──────────────────────────────────────
        if request.user.is_authenticated and lesson.contract.user == request.user:
            display_name = (request.user.get_full_name() or request.user.username) + " (Tutor)"
            return render(
                request,
                self.template_name,
                {
                    "room": room,
                    "lesson": lesson,
                    "display_name": display_name,
                    "documents": lesson.documents.all(),
                    "is_tutor": True,
                    "back_url": f"/lessons/{lesson.pk}/",
                    "MEETING_TURN_SERVERS": turn_servers,
                },
            )

        # ── 3. Nicht eingeloggt → Portal-Login mit Rücksprung ─────────────────
        return redirect("/portal/login/?" + urlencode({"next": request.path}))
