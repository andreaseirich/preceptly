"""
Views für Meeting-Räume (Tutor + Portal-Nutzer).
"""

import logging
import os
import uuid
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.core.upload_validation import sanitize_doc_name, validate_file_magic
from apps.lessons.models import Session, SessionDocument
from apps.meeting.models import MeetingRoom
from apps.portal.models import ParentStudentLink
from apps.portal.views import get_portal_user

logger = logging.getLogger(__name__)


class StartMeetingView(LoginRequiredMixin, View):
    """Tutor startet/betritt ein Meeting für eine bestimmte Stunde."""

    def get(self, request, lesson_pk):
        lesson = get_object_or_404(Session, pk=lesson_pk, contract__user=request.user)
        with transaction.atomic():
            room, _ = MeetingRoom.objects.select_for_update().get_or_create(lesson=lesson)
            if not room.is_active:
                room.is_active = True
                room.save(update_fields=["is_active"])
        return redirect("meeting:room", token=room.token)

    def post(self, request, lesson_pk):
        return self.get(request, lesson_pk)


class MeetingDocumentUploadView(View):
    """AJAX-Dokumenten-Upload im Meeting-Raum. Für Tutor und Portal-Nutzer."""

    def post(self, request, token):
        # Auth-Check ZUERST, bevor Datei gelesen wird (DoS-Schutz)
        portal_user = get_portal_user(request)
        if not portal_user and not request.user.is_authenticated:
            return JsonResponse({"error": "Nicht authentifiziert"}, status=401)

        room = get_object_or_404(MeetingRoom, token=token, is_active=True)
        lesson = room.lesson

        # Zugangsprüfung (autorisierter Teilnehmer dieses Meetings?)
        if portal_user:
            ok = ParentStudentLink.objects.filter(
                parent=portal_user, contract=lesson.contract, is_active=True
            ).exists()
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
        if not validate_file_magic(file, ext):
            return JsonResponse({"error": "File type not allowed."}, status=400)
        if file.size > _MAX_UPLOAD_SIZE:
            return JsonResponse({"error": "File too large (max 50 MB)."}, status=400)

        name = sanitize_doc_name(request.POST.get("name", "").strip() or file.name)
        doc = SessionDocument.objects.create(session=lesson, file=file, name=name)
        safe_name = name.replace("\n", " ").replace("\r", " ")
        logger.info("Dokument hochgeladen: %s (lesson %s)", safe_name, lesson.pk)

        return JsonResponse(
            {
                "ok": True,
                "id": doc.pk,
                "name": doc.name or doc.file.name,
                "file_name": os.path.basename(doc.file.name),
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
            ok = ParentStudentLink.objects.filter(
                parent=portal_user, contract=lesson.contract, is_active=True
            ).exists()
        elif request.user.is_authenticated and lesson.contract.user == request.user:
            ok = True
        else:
            ok = False

        if not ok:
            return HttpResponseForbidden()

        doc = get_object_or_404(SessionDocument, pk=doc_pk, session=lesson)
        content_type, _ = mimetypes.guess_type(doc.file.name)
        effective_ct = content_type or "application/octet-stream"

        raw_name = doc.name or doc.file.name
        # Sicherheitsbereinigung: Steuerzeichen und problematische Sonderzeichen entfernen
        safe_name = (
            raw_name.replace('"', "")
            .replace("\r", "")
            .replace("\n", "")
            .replace("\\", "_")
            .replace(";", "_")
        )
        # ASCII-Fallback-Name für filename-Parameter (RFC 5987)
        ascii_name = safe_name.encode("ascii", "ignore").decode("ascii").strip()
        ascii_name = ascii_name or "file"

        is_inline = effective_ct.startswith("image/") or effective_ct == "application/pdf"
        disposition_type = "inline" if is_inline else "attachment"
        serve_ct = effective_ct if is_inline else "application/octet-stream"

        # RFC 5987: filename* für korrekte Unicode-Unterstützung
        disposition = (
            f"{disposition_type}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(safe_name)}"
        )

        response = FileResponse(doc.file.open("rb"), content_type=serve_ct)
        response["Content-Disposition"] = disposition
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = (
            "default-src 'none'; img-src 'self'; object-src 'self'"
        )
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


class MeetingDocumentDeleteView(View):
    """Löscht ein Meeting-Dokument. Nur für Tutor und Portal-Nutzer mit Zugriff auf die Stunde."""

    def post(self, request, token, doc_pk):
        room = get_object_or_404(MeetingRoom, token=token, is_active=True)
        lesson = room.lesson

        portal_user = get_portal_user(request)
        if portal_user:
            ok = ParentStudentLink.objects.filter(
                parent=portal_user, contract=lesson.contract, is_active=True
            ).exists()
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

        with transaction.atomic():
            room = get_object_or_404(
                MeetingRoom.objects.select_for_update(),
                token=token,
                lesson__contract__user=request.user,
            )
            room.is_active = False
            room.token = uuid.uuid4()
            room.save(update_fields=["is_active", "token"])

        safe_token = str(token).replace("\n", " ").replace("\r", " ")
        safe_user = str(request.user).replace("\n", " ").replace("\r", " ")
        logger.info("Meeting %s beendet durch %s", safe_token, safe_user)
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
        import json as _json

        turn_servers = _json.dumps(getattr(settings, "MEETING_ICE_SERVERS", []))

        # ── 1. Tutor-Zugang zuerst prüfen (höchste Priorität) ─────────────────
        # Tutor-Check kommt vor Portal-Check, damit ein Tutor mit aktiver Portal-
        # Session im selben Browser nicht fälschlicherweise als Portal-Nutzer
        # behandelt und mit "Kein Zugriff" abgewiesen wird.
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

        # ── 2. Portal-Nutzer (Ein-Kind-Konto / Familien-Konto) ────────────────
        portal_user = get_portal_user(request)
        if portal_user:
            from apps.portal.views import _get_default_portal_student

            has_access = ParentStudentLink.objects.filter(
                parent=portal_user, contract=lesson.contract, is_active=True
            ).exists()
            if not has_access:
                return HttpResponseForbidden("Kein Zugriff auf dieses Meeting.")

            # Ein-Kind-Konto: eigener Name + eigene Stunden-URL.
            # Familien-Konto (0 oder 2+ Kinder): Name des Kontoinhabers + Familienübersicht.
            default_student = _get_default_portal_student(portal_user)
            if default_student and default_student.pk == lesson.contract.pk:
                display_name = lesson.contract.full_name
                back_url = f"/portal/student/lessons/{lesson.pk}/"
            else:
                display_name = (
                    portal_user.user.get_full_name() or portal_user.user.username
                ) + " (Elternteil)"
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

        # ── 3. Nicht eingeloggt → Portal-Login mit validiertem Rücksprung ──────
        next_path = request.path
        from django.utils.http import url_has_allowed_host_and_scheme

        if not url_has_allowed_host_and_scheme(
            next_path,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_path = "/portal/"
        login_url = reverse("portal:login")
        return redirect(login_url + "?" + urlencode({"next": next_path}))
