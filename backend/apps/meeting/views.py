"""
Views für Meeting-Räume (Tutor + Portal-Nutzer).
"""

import logging
import os
import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.lessons.models import Session, SessionDocument
from apps.meeting.models import MeetingRoom
from apps.portal.models import ParentStudentLink, StudentPortalLink
from apps.portal.views import get_portal_user

logger = logging.getLogger(__name__)


def _validate_file_magic(file, ext: str) -> bool:
    _MAGIC = {
        ".pdf": [(0, b"%PDF")],
        ".jpg": [(0, b"\xff\xd8\xff")],
        ".jpeg": [(0, b"\xff\xd8\xff")],
        ".png": [(0, b"\x89PNG\r\n\x1a\n")],
        ".gif": [(0, b"GIF87a"), (0, b"GIF89a")],
        ".webp": [(0, b"RIFF"), (8, b"WEBP")],
        ".docx": [(0, b"PK\x03\x04")],
        ".xlsx": [(0, b"PK\x03\x04")],
        ".pptx": [(0, b"PK\x03\x04")],
        ".mp3": [(0, b"ID3"), (0, b"\xff\xfb"), (0, b"\xff\xf3"), (0, b"\xff\xf2")],
        ".mp4": [(4, b"ftyp")],
    }
    if ext == ".txt":
        return True
    checks = _MAGIC.get(ext)
    if not checks:
        return False
    header = file.read(12)
    file.seek(0)
    if ext == ".webp":
        return all(header[offset : offset + len(sig)] == sig for offset, sig in checks)
    return any(header[offset : offset + len(sig)] == sig for offset, sig in checks)


class StartMeetingView(LoginRequiredMixin, View):
    """Tutor startet/betritt ein Meeting für eine bestimmte Stunde."""

    def get(self, request, lesson_pk):
        lesson = get_object_or_404(Session, pk=lesson_pk, contract__user=request.user)
        room, _ = MeetingRoom.objects.get_or_create(lesson=lesson)
        if not room.is_active:
            room.is_active = True
            room.save(update_fields=["is_active"])
        return redirect("meeting:room", token=room.token)

    def post(self, request, lesson_pk):
        return self.get(request, lesson_pk)


class MeetingDocumentUploadView(View):
    """AJAX-Dokumenten-Upload im Meeting-Raum. Für Tutor und Portal-Nutzer."""

    def post(self, request, token):
        room = get_object_or_404(MeetingRoom, token=token, is_active=True)
        lesson = room.lesson

        # Zugangsprüfung
        portal_user = get_portal_user(request)
        if portal_user:
            if portal_user.role == "student":
                ok = StudentPortalLink.objects.filter(
                    portal_user=portal_user, is_active=True, contract=lesson.contract
                ).exists()
            elif portal_user.role == "parent":
                ok = ParentStudentLink.objects.filter(
                    parent=portal_user, contract=lesson.contract
                ).exists()
            else:
                ok = False
        elif request.user.is_authenticated and lesson.contract.user == request.user:
            ok = True
        else:
            ok = False

        if not ok:
            return JsonResponse({"error": "Kein Zugriff"}, status=403)

        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "Keine Datei"}, status=400)

        _ALLOWED_MEETING_EXTENSIONS = {
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".txt",
            ".docx",
            ".xlsx",
            ".pptx",
            ".mp3",
            ".mp4",
        }
        _MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in _ALLOWED_MEETING_EXTENSIONS:
            return JsonResponse({"error": "File type not allowed."}, status=400)
        if not _validate_file_magic(file, ext):
            return JsonResponse({"error": "File type not allowed."}, status=400)
        if file.size > _MAX_UPLOAD_SIZE:
            return JsonResponse({"error": "File too large (max 50 MB)."}, status=400)

        name = request.POST.get("name", "").strip() or file.name
        doc = SessionDocument.objects.create(session=lesson, file=file, name=name)
        safe_name = name.replace("\n", " ").replace("\r", " ")
        logger.info("Dokument hochgeladen: %s (lesson %s)", safe_name, lesson.pk)

        return JsonResponse(
            {
                "ok": True,
                "id": doc.pk,
                "name": doc.name or doc.file.name,
                "url": reverse(
                    "meeting:doc_serve",
                    kwargs={"token": str(lesson.meeting_room.token), "doc_pk": doc.pk},
                ),
                "date": doc.uploaded_at.strftime("%d.%m.%Y"),
            }
        )


class MeetingDocumentServeView(View):
    """Liefert Meeting-Dokumente mit Auth-Check (umgeht Nginx-Media-Probleme)."""

    def get(self, request, token, doc_pk):
        import mimetypes

        from django.http import FileResponse

        room = get_object_or_404(MeetingRoom, token=token, is_active=True)
        lesson = room.lesson
        portal_user = get_portal_user(request)

        if portal_user:
            if portal_user.role == "student":
                ok = StudentPortalLink.objects.filter(
                    portal_user=portal_user, is_active=True, contract=lesson.contract
                ).exists()
            elif portal_user.role == "parent":
                ok = ParentStudentLink.objects.filter(
                    parent=portal_user, contract=lesson.contract
                ).exists()
            else:
                ok = False
        elif request.user.is_authenticated and lesson.contract.user == request.user:
            ok = True
        else:
            ok = False

        if not ok:
            return HttpResponseForbidden()

        doc = get_object_or_404(SessionDocument, pk=doc_pk, session=lesson)
        content_type, _ = mimetypes.guess_type(doc.file.name)
        effective_ct = content_type or "application/octet-stream"
        safe_name = (doc.name or doc.file.name).replace('"', "").replace("\r", "").replace("\n", "")
        is_inline = effective_ct.startswith("image/") or effective_ct == "application/pdf"
        if is_inline:
            disposition = f'inline; filename="{safe_name}"'
            serve_ct = effective_ct
        else:
            disposition = f'attachment; filename="{safe_name}"'
            serve_ct = "application/octet-stream"
        response = FileResponse(doc.file.open("rb"), content_type=serve_ct)
        response["Content-Disposition"] = disposition
        return response


class MeetingDocumentDeleteView(View):
    """Löscht ein Meeting-Dokument. Nur für Tutor und Portal-Nutzer mit Zugriff auf die Stunde."""

    def post(self, request, token, doc_pk):
        room = get_object_or_404(MeetingRoom, token=token, is_active=True)
        lesson = room.lesson

        portal_user = get_portal_user(request)
        if portal_user:
            if portal_user.role == "student":
                ok = StudentPortalLink.objects.filter(
                    portal_user=portal_user, is_active=True, contract=lesson.contract
                ).exists()
            elif portal_user.role == "parent":
                ok = ParentStudentLink.objects.filter(
                    parent=portal_user, contract=lesson.contract
                ).exists()
            else:
                ok = False
        elif request.user.is_authenticated and lesson.contract.user == request.user:
            ok = True
        else:
            ok = False

        if not ok:
            return JsonResponse({"error": "Kein Zugriff"}, status=403)

        doc = get_object_or_404(SessionDocument, pk=doc_pk, session=lesson)
        doc.file.delete(save=False)
        doc.delete()
        return JsonResponse({"ok": True})


class EndMeetingView(LoginRequiredMixin, View):
    """Tutor beendet ein Meeting (setzt is_active=False). Wird per fetch() aufgerufen."""

    def post(self, request, token):
        from django.http import JsonResponse

        room = get_object_or_404(MeetingRoom, token=token, lesson__contract__user=request.user)
        room.is_active = False
        room.token = uuid.uuid4()
        room.save(update_fields=["is_active", "token"])
        safe_token = str(token).replace("\n", " ").replace("\r", " ")
        logger.info("Meeting %s beendet durch %s", safe_token, request.user)
        return JsonResponse({"ok": True})


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
                    "user_token": f"portal_{portal_user.pk}",
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
                    "user_token": f"tutor_{request.user.pk}",
                    "MEETING_TURN_SERVERS": turn_servers,
                },
            )

        # ── 3. Nicht eingeloggt → Portal-Login mit Rücksprung ─────────────────
        return redirect("/portal/login/?" + urlencode({"next": request.path}))
