import datetime as _dt
import logging
import os
import uuid
from calendar import monthcalendar as _monthcalendar

from django.contrib import messages
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views import View
from django_ratelimit.decorators import ratelimit

from apps.lessons.models import Lesson as _Lesson
from apps.portal.models import ParentStudentLink, PortalMessage, PortalUser, StudentPortalLink

logger = logging.getLogger(__name__)

_ALLOWED_UPLOAD_EXTENSIONS = {
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
_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def get_portal_user(request):
    """Return PortalUser from session or None."""
    portal_user_id = request.session.get("portal_user_id")
    if not portal_user_id:
        return None
    try:
        return PortalUser.objects.select_related("user", "tutor").get(pk=portal_user_id)
    except PortalUser.DoesNotExist:
        return None


class PortalLoginView(View):
    template_name = "portal/login.html"

    def get(self, request):
        if get_portal_user(request):
            next_url = request.GET.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("portal:home")
        return render(request, self.template_name, {"next": request.GET.get("next", "")})

    @method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True))
    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        error = None
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                portal_user = PortalUser.objects.get(user=user)
                request.session["portal_user_id"] = portal_user.pk
                next_url = request.POST.get("next", "")
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect("portal:home")
            else:
                error = _("Ungültige Zugangsdaten.")
        except (User.DoesNotExist, PortalUser.DoesNotExist):
            error = _("Ungültige Zugangsdaten.")
        return render(request, self.template_name, {"error": error})


class PortalLogoutView(View):
    def post(self, request):
        request.session.pop("portal_user_id", None)
        return redirect("portal:login")


class PortalDispatchView(View):
    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        if portal_user.role == "student":
            return redirect("portal:student_home")
        return redirect("portal:parent_home")


class StudentHomeView(View):
    template_name = "portal/student_home.html"

    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user or portal_user.role != "student":
            return redirect("portal:login")
        link = get_object_or_404(StudentPortalLink, portal_user=portal_user, is_active=True)
        if link.contract.user != portal_user.tutor:
            return HttpResponseForbidden()
        student = link.contract
        import datetime

        from apps.lessons.models import Lesson

        today = datetime.date.today()
        upcoming = Lesson.objects.filter(
            contract=student,
            date__gte=today,
            status__in=["planned"],
        ).order_by("date", "start_time")[:5]
        recent = Lesson.objects.filter(
            contract=student,
            date__lt=today,
        ).order_by("-date", "-start_time")[:5]
        chat_messages = PortalMessage.objects.filter(contract=student).order_by("created_at")
        PortalMessage.objects.filter(contract=student, read_by_portal=False).update(
            read_by_portal=True
        )
        upcoming_with_meeting = []
        for lesson in upcoming:
            room = None
            try:
                if lesson.meeting_room.is_active:
                    room = lesson.meeting_room
            except Exception:  # noqa: S110 – RelatedObjectDoesNotExist bei fehlendem MeetingRoom
                pass
            upcoming_with_meeting.append({"lesson": lesson, "meeting_room": room})

        return render(
            request,
            self.template_name,
            {
                "student": student,
                "upcoming": upcoming,
                "upcoming_with_meeting": upcoming_with_meeting,
                "recent": recent,
                "chat_messages": chat_messages,
                "portal_user": portal_user,
            },
        )


class StudentLessonListView(View):
    template_name = "portal/student_lessons.html"

    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user or portal_user.role != "student":
            return redirect("portal:login")
        link = get_object_or_404(StudentPortalLink, portal_user=portal_user, is_active=True)
        if link.contract.user != portal_user.tutor:
            return HttpResponseForbidden()
        from apps.lessons.models import Lesson

        lessons = Lesson.objects.filter(
            contract=link.contract,
        ).order_by("-date", "-start_time")
        return render(
            request,
            self.template_name,
            {
                "student": link.contract,
                "lessons": lessons,
                "portal_user": portal_user,
            },
        )


class ParentHomeView(View):
    template_name = "portal/parent_home.html"

    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user or portal_user.role != "parent":
            return redirect("portal:login")
        today = _dt.date.today()
        upcoming_qs = (
            _Lesson.objects.filter(
                date__gte=today,
                status__in=["planned"],
            )
            .order_by("date", "start_time")
            .select_related("meeting_room")
        )

        links = (
            ParentStudentLink.objects.filter(parent=portal_user)
            .select_related("contract")
            .annotate(
                unread_count=Count(
                    "contract__portalmessage",
                    filter=Q(contract__portalmessage__read_by_portal=False),
                )
            )
            .prefetch_related(
                Prefetch(
                    "contract__sessions",
                    queryset=upcoming_qs,
                    to_attr="_upcoming_lessons",
                )
            )
        )

        def _get_upcoming(link):
            lessons = getattr(link.contract, "_upcoming_lessons", [])
            return lessons[0] if lessons else None

        def _get_meeting_room(upcoming):
            if not upcoming:
                return None
            try:
                return upcoming.meeting_room if upcoming.meeting_room.is_active else None
            except Exception:  # noqa: S110
                return None

        students_data = [
            {
                "student": link.contract,
                "next_lesson": _get_upcoming(link),
                "unread_messages": link.unread_count,
                "meeting_room": _get_meeting_room(_get_upcoming(link)),
            }
            for link in links
        ]
        return render(
            request,
            self.template_name,
            {
                "students_data": students_data,
                "portal_user": portal_user,
            },
        )


class ParentStudentDetailView(View):
    template_name = "portal/parent_student_detail.html"

    def get(self, request, student_pk):
        portal_user = get_portal_user(request)
        if not portal_user or portal_user.role != "parent":
            return redirect("portal:login")
        link = get_object_or_404(ParentStudentLink, parent=portal_user, contract_id=student_pk)
        student = link.contract
        from apps.lessons.models import Lesson

        lessons = Lesson.objects.filter(
            contract=student,
        ).order_by("-date", "-start_time")[:20]
        progress_notes = student.progress_notes.all()[:10]
        chat_messages = PortalMessage.objects.filter(contract=student).order_by("created_at")
        PortalMessage.objects.filter(contract=student, read_by_portal=False).update(
            read_by_portal=True
        )
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "lessons": lessons,
                "progress_notes": progress_notes,
                "chat_messages": chat_messages,
                "portal_user": portal_user,
            },
        )


class PortalMessageView(View):
    template_name = "portal/messages.html"

    def _get_student_for_portal_user(self, portal_user, student_pk):
        if portal_user.role == "student":
            link = StudentPortalLink.objects.filter(
                portal_user=portal_user, is_active=True, contract_id=student_pk
            ).first()
            if link and link.contract.user != portal_user.tutor:
                return None
            return link.contract if link else None
        else:
            link = ParentStudentLink.objects.filter(
                parent=portal_user, contract_id=student_pk
            ).first()
            if link and link.contract.user != portal_user.tutor:
                return None
            return link.contract if link else None

    def get(self, request, student_pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = self._get_student_for_portal_user(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        chat_messages = PortalMessage.objects.filter(contract=student).order_by("created_at")
        PortalMessage.objects.filter(contract=student, read_by_portal=False).update(
            read_by_portal=True
        )
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "chat_messages": chat_messages,
                "portal_user": portal_user,
            },
        )

    def post(self, request, student_pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = self._get_student_for_portal_user(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        text = request.POST.get("text", "").strip()
        if text:
            PortalMessage.objects.create(
                sender_portal_user=portal_user,
                sender_is_tutor=False,
                contract=student,
                text=text,
            )
        return redirect("portal:messages", student_pk=student_pk)


class PortalActivateView(View):
    """Token-based activation: user sets own password, link becomes active.

    Works for both StudentPortalLink (student) and ParentStudentLink (parent).
    """

    template_name = "portal/activate.html"

    def _get_link(self, token):
        from datetime import timedelta

        from django.db.models import Q
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(hours=72)
        valid = Q(invite_token_created_at__isnull=True) | Q(invite_token_created_at__gte=cutoff)
        link = StudentPortalLink.objects.filter(invite_token=token).filter(valid).first()
        if link:
            return link, link.portal_user
        link = ParentStudentLink.objects.filter(invite_token=token).filter(valid).first()
        if link:
            return link, link.parent
        return None, None

    def get(self, request, token):
        link, portal_user = self._get_link(token)
        if link is None:
            from django.http import Http404

            raise Http404
        if link.is_active:
            return redirect("portal:login")
        return render(request, self.template_name, {"token": token, "student": link.contract})

    def post(self, request, token):
        link, portal_user = self._get_link(token)
        if link is None:
            from django.http import Http404

            raise Http404
        if link.is_active:
            return redirect("portal:login")
        password = request.POST.get("password", "").strip()
        password2 = request.POST.get("password_confirm", "").strip()
        if len(password) < 8:
            return render(
                request,
                self.template_name,
                {
                    "token": token,
                    "student": link.contract,
                    "error": "Das Passwort muss mindestens 8 Zeichen lang sein.",
                },
            )
        if password != password2:
            return render(
                request,
                self.template_name,
                {
                    "token": token,
                    "student": link.contract,
                    "error": "Die Passwörter stimmen nicht überein.",
                },
            )
        portal_user.user.set_password(password)
        portal_user.user.save()
        link.is_active = True
        link.save()
        request.session["portal_user_id"] = portal_user.pk
        return redirect("portal:home")


class PortalPasswordResetRequestView(View):
    template_name = "portal/password_reset.html"

    def get(self, request):
        return render(request, self.template_name)

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        username = request.POST.get("username", "").strip()
        try:
            user = User.objects.get(username=username)
            portal_user = PortalUser.objects.get(user=user)
            # Reuse invite_token mechanism for reset
            if portal_user.role == "student":
                link = StudentPortalLink.objects.get(portal_user=portal_user)
            else:
                # Parent: use ParentStudentLink (not StudentPortalLink)
                link = ParentStudentLink.objects.filter(parent=portal_user).first()
            if link:
                link.invite_token = uuid.uuid4().hex
                link.save()
                # Get recipient email: user.email if available, else student.email
                recipient = user.email or link.contract.email
                if recipient:
                    from django.conf import settings
                    from django.core.mail import send_mail
                    from django.template.loader import render_to_string

                    site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
                    reset_url = f"{site_url}/portal/activate/{link.invite_token}/"
                    context = {
                        "student": link.contract,
                        "reset_url": reset_url,
                        "site_url": site_url,
                    }
                    html = render_to_string("portal/email/password_reset.html", context)
                    plain = render_to_string("portal/email/password_reset.txt", context)
                    send_mail(
                        subject="Reset your Preceptly Portal password",
                        message=plain,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient],
                        html_message=html,
                        fail_silently=True,
                    )
        except (
            User.DoesNotExist,
            PortalUser.DoesNotExist,
            StudentPortalLink.DoesNotExist,
            ParentStudentLink.DoesNotExist,
        ):
            pass  # Don't reveal if user exists
        return render(request, self.template_name, {"sent": True})


class StudentLessonDetailView(View):
    template_name = "portal/student_lesson_detail.html"

    def get(self, request, pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")

        from apps.lessons.models import Lesson

        if portal_user.role == "student":
            link = get_object_or_404(StudentPortalLink, portal_user=portal_user, is_active=True)
            if link.contract.user != portal_user.tutor:
                return HttpResponseForbidden()
            lesson = get_object_or_404(Lesson, pk=pk, contract=link.contract)
            student = link.contract
        elif portal_user.role == "parent":
            # Elternteil kann Stunden aller verknüpften Kinder sehen
            parent_links = ParentStudentLink.objects.filter(parent=portal_user)
            contract_ids = list(parent_links.values_list("contract_id", flat=True))
            lesson = get_object_or_404(Lesson, pk=pk, contract_id__in=contract_ids)
            student = lesson.contract
        else:
            return redirect("portal:login")

        return render(
            request,
            self.template_name,
            {
                "lesson": lesson,
                "student": student,
                "portal_user": portal_user,
            },
        )


# ════════════════════════════════════════════════════════════════════════
# Portal Booking / Scheduling / Documents
# ════════════════════════════════════════════════════════════════════════


def _get_portal_student(portal_user, student_pk):
    """Gibt den Schüler zurück, falls portal_user Zugriff hat, sonst None."""
    if portal_user.role == "student":
        link = StudentPortalLink.objects.filter(
            portal_user=portal_user, is_active=True, contract_id=student_pk
        ).first()
        if not link or link.contract.user != portal_user.tutor:
            return None
        return link.contract
    else:
        link = ParentStudentLink.objects.filter(parent=portal_user, contract_id=student_pk).first()
        if not link or link.contract.user != portal_user.tutor:
            return None
        return link.contract


def _get_active_contract(student):
    """Gibt den neuesten aktiven Vertrag des Schülers zurück."""
    today = _dt.date.today()
    return (
        student.contracts.filter(is_active=True)
        .filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=today))
        .order_by("-start_date")
        .first()
    )


def _get_available_slots(tutor, date, duration_minutes=60, slot_interval=30):
    """Gibt sortierte Liste freier Startzeiten (HH:MM) zurück."""
    from apps.lessons.models import Session as _Session

    profile = getattr(tutor, "profile", None)
    wh = (profile.default_working_hours if profile else {}) or {}
    day_name = date.strftime("%A").lower()
    day_slots = wh.get(day_name, [])

    sessions = _Session.objects.filter(
        contract__user=tutor,
        date=date,
        status__in=["planned", "taught", "paid"],
    )
    busy = []
    for s in sessions:
        s_start = _dt.datetime.combine(date, s.start_time)
        s_end = s_start + _dt.timedelta(minutes=s.duration_minutes)
        busy.append((s.start_time, s_end.time()))

    available = []
    for slot in day_slots:
        try:
            slot_start = _dt.datetime.strptime(slot["start"], "%H:%M").time()
            slot_end = _dt.datetime.strptime(slot["end"], "%H:%M").time()
        except (KeyError, ValueError):
            continue
        cur = _dt.datetime.combine(date, slot_start)
        slot_end_dt = _dt.datetime.combine(date, slot_end)
        dur = _dt.timedelta(minutes=duration_minutes)
        step = _dt.timedelta(minutes=slot_interval)
        while cur + dur <= slot_end_dt:
            cs = cur.time()
            ce = (cur + dur).time()
            if not any(cs < be and ce > bs for bs, be in busy):
                available.append(cs.strftime("%H:%M"))
            cur += step
    return sorted(set(available))


class PortalAvailabilityView(View):
    """JSON-API: gibt freie Zeitslots für ein Datum zurück."""

    def get(self, request, student_pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return JsonResponse({"error": "Nicht angemeldet"}, status=401)
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return JsonResponse({"error": "Kein Zugriff"}, status=403)
        contract = _get_active_contract(student)
        duration = contract.unit_duration_minutes if contract else 60

        date_str = request.GET.get("date", "")
        try:
            date = _dt.date.fromisoformat(date_str)
        except ValueError:
            return JsonResponse({"error": "Ungültiges Datum"}, status=400)

        slots = _get_available_slots(student.user, date, duration_minutes=duration)
        return JsonResponse({"slots": slots, "duration_minutes": duration})


class PortalBookingView(View):
    """Terminbuchung aus dem Portal."""

    template_name = "portal/book.html"

    def _render(self, request, student, contract, error=None, success=None):
        today = _dt.date.today()
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "contract": contract,
                "error": error,
                "success": success,
                "today": today.isoformat(),
                "portal_user": get_portal_user(request),
            },
        )

    def get(self, request, student_pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        contract = _get_active_contract(student)
        return self._render(request, student, contract)

    def post(self, request, student_pk):
        from apps.lessons.models import Session as _Session

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        contract = _get_active_contract(student)
        if not contract:
            return self._render(request, student, None, error="Kein aktiver Vertrag gefunden.")

        date_str = request.POST.get("date", "").strip()
        time_str = request.POST.get("start_time", "").strip()
        topic = request.POST.get("topic", "").strip()

        try:
            session_date = _dt.date.fromisoformat(date_str)
            session_time = _dt.time.fromisoformat(time_str)
        except ValueError:
            return self._render(request, student, contract, error="Ungültiges Datum oder Uhrzeit.")

        if session_date < _dt.date.today():
            return self._render(
                request, student, contract, error="Das Datum liegt in der Vergangenheit."
            )

        # Konflikt-Prüfung
        duration = contract.unit_duration_minutes
        start_dt = _dt.datetime.combine(session_date, session_time)
        end_dt = start_dt + _dt.timedelta(minutes=duration)
        existing = _Session.objects.filter(
            contract__user=student.user,
            date=session_date,
            status__in=["planned", "taught", "paid"],
        )
        for ex in existing:
            ex_start = _dt.datetime.combine(session_date, ex.start_time)
            ex_end = ex_start + _dt.timedelta(minutes=ex.duration_minutes)
            if start_dt < ex_end and end_dt > ex_start:
                return self._render(
                    request,
                    student,
                    contract,
                    error=f"Zeitkonflikt mit bestehendem Termin um {ex.start_time.strftime('%H:%M')} Uhr.",
                )

        _Session.objects.create(
            contract=contract,
            date=session_date,
            start_time=session_time,
            duration_minutes=duration,
            status="planned",
            notes=topic or None,
            created_via="portal_booking",
        )
        return self._render(
            request,
            student,
            contract,
            success=f"Termin am {session_date.strftime('%d.%m.%Y')} um {session_time.strftime('%H:%M')} Uhr gebucht.",
        )


class PortalSessionCancelView(View):
    """Termin absagen."""

    def post(self, request, session_pk):
        from apps.lessons.models import Session as _Session

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")

        session = get_object_or_404(_Session, pk=session_pk)
        student = _get_portal_student(portal_user, session.contract_id)
        if not student:
            return HttpResponseForbidden()
        if session.status != "planned":
            messages.warning(request, "Nur geplante Termine können abgesagt werden.")
        else:
            session.status = "cancelled"
            session.save()
            messages.success(
                request, f"Termin am {session.date.strftime('%d.%m.%Y')} wurde abgesagt."
            )

        # Zurück zur richtigen Übersicht
        if portal_user.role == "student":
            return redirect("portal:student_lessons")
        return redirect("portal:parent_student_detail", student_pk=student.pk)


class PortalSessionRescheduleView(View):
    """Termin verschieben."""

    template_name = "portal/reschedule.html"

    def _get_session_and_student(self, request, session_pk):
        from apps.lessons.models import Session as _Session

        portal_user = get_portal_user(request)
        if not portal_user:
            return None, None, None
        session = get_object_or_404(_Session, pk=session_pk)
        student = _get_portal_student(portal_user, session.contract_id)
        return portal_user, session, student

    def get(self, request, session_pk):
        portal_user, session, student = self._get_session_and_student(request, session_pk)
        if not portal_user:
            return redirect("portal:login")
        if not student:
            return HttpResponseForbidden()
        return render(
            request,
            self.template_name,
            {
                "session": session,
                "student": student,
                "portal_user": portal_user,
                "today": _dt.date.today().isoformat(),
            },
        )

    def post(self, request, session_pk):
        from apps.lessons.models import Session as _Session

        portal_user, session, student = self._get_session_and_student(request, session_pk)
        if not portal_user:
            return redirect("portal:login")
        if not student:
            return HttpResponseForbidden()
        if session.status != "planned":
            messages.warning(request, "Nur geplante Termine können verschoben werden.")
            if portal_user.role == "student":
                return redirect("portal:student_lessons")
            return redirect("portal:parent_student_detail", student_pk=student.pk)

        date_str = request.POST.get("date", "").strip()
        time_str = request.POST.get("start_time", "").strip()
        try:
            new_date = _dt.date.fromisoformat(date_str)
            new_time = _dt.time.fromisoformat(time_str)
        except ValueError:
            return render(
                request,
                self.template_name,
                {
                    "session": session,
                    "student": student,
                    "portal_user": portal_user,
                    "today": _dt.date.today().isoformat(),
                    "error": "Ungültiges Datum oder Uhrzeit.",
                },
            )

        if new_date < _dt.date.today():
            return render(
                request,
                self.template_name,
                {
                    "session": session,
                    "student": student,
                    "portal_user": portal_user,
                    "today": _dt.date.today().isoformat(),
                    "error": "Das Datum liegt in der Vergangenheit.",
                },
            )

        # Konflikt-Prüfung (außer sich selbst)
        duration = session.duration_minutes
        start_dt = _dt.datetime.combine(new_date, new_time)
        end_dt = start_dt + _dt.timedelta(minutes=duration)
        conflicts = _Session.objects.filter(
            contract__user=student.user,
            date=new_date,
            status__in=["planned", "taught", "paid"],
        ).exclude(pk=session.pk)
        for ex in conflicts:
            ex_start = _dt.datetime.combine(new_date, ex.start_time)
            ex_end = ex_start + _dt.timedelta(minutes=ex.duration_minutes)
            if start_dt < ex_end and end_dt > ex_start:
                return render(
                    request,
                    self.template_name,
                    {
                        "session": session,
                        "student": student,
                        "portal_user": portal_user,
                        "today": _dt.date.today().isoformat(),
                        "error": f"Zeitkonflikt mit Termin um {ex.start_time.strftime('%H:%M')} Uhr.",
                    },
                )

        old_date = session.date
        session.date = new_date
        session.start_time = new_time
        # Aus Serienbindung lösen wenn verschoben
        session.recurring_session = None
        session.save()
        messages.success(
            request,
            f"Termin vom {old_date.strftime('%d.%m.%Y')} auf {new_date.strftime('%d.%m.%Y')} um {new_time.strftime('%H:%M')} Uhr verschoben.",
        )
        if portal_user.role == "student":
            return redirect("portal:student_lessons")
        return redirect("portal:parent_student_detail", student_pk=student.pk)


class PortalRecurringManageView(View):
    """Serientermine eines Schülers verwalten."""

    template_name = "portal/recurring_manage.html"

    def get(self, request, student_pk):
        from apps.lessons.recurring_models import RecurringSession

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        contract = _get_active_contract(student)
        series = RecurringSession.objects.filter(
            contract=student,
            is_active=True,
        ).order_by("start_date")
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "series": series,
                "contract": contract,
                "portal_user": portal_user,
            },
        )


class PortalRecurringCreateView(View):
    """Neuen Serientermin erstellen."""

    template_name = "portal/recurring_form.html"

    WEEKDAY_FIELDS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    WEEKDAY_LABELS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    def get(self, request, student_pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        contract = _get_active_contract(student)
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "contract": contract,
                "portal_user": portal_user,
                "weekday_fields": list(zip(self.WEEKDAY_FIELDS, self.WEEKDAY_LABELS, strict=True)),
                "today": _dt.date.today().isoformat(),
            },
        )

    def post(self, request, student_pk):
        from apps.lessons.recurring_models import RecurringSession
        from apps.lessons.recurring_service import RecurringSessionService

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        contract = _get_active_contract(student)
        if not contract:
            messages.warning(request, "Kein aktiver Vertrag vorhanden.")
            return redirect("portal:recurring_manage", student_pk=student_pk)

        time_str = request.POST.get("start_time", "").strip()
        start_str = request.POST.get("start_date", "").strip()
        end_str = request.POST.get("end_date", "").strip()
        rec_type = request.POST.get("recurrence_type", "weekly")
        topic = request.POST.get("topic", "").strip()

        try:
            start_time = _dt.time.fromisoformat(time_str)
            start_date = _dt.date.fromisoformat(start_str)
        except ValueError:
            messages.warning(request, "Ungültige Zeit oder Startdatum.")
            return redirect("portal:recurring_create", student_pk=student_pk)

        end_date = None
        if end_str:
            try:
                end_date = _dt.date.fromisoformat(end_str)
            except ValueError as exc:
                logger.debug("Invalid end_date format ignored: %s", exc)

        weekdays = {f: (f in request.POST) for f in self.WEEKDAY_FIELDS}
        if not any(weekdays.values()):
            messages.warning(request, "Bitte mindestens einen Wochentag auswählen.")
            return redirect("portal:recurring_create", student_pk=student_pk)

        rs = RecurringSession.objects.create(
            contract=contract,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            duration_minutes=contract.unit_duration_minutes,
            recurrence_type=rec_type if rec_type in ("weekly", "biweekly", "monthly") else "weekly",
            notes=topic or None,
            is_active=True,
            **weekdays,
        )
        result = RecurringSessionService.generate_sessions(rs, check_conflicts=False)
        messages.success(request, f"Serientermin erstellt. {result['created']} Termine generiert.")
        return redirect("portal:recurring_manage", student_pk=student_pk)


class PortalRecurringCancelView(View):
    """Serientermin deaktivieren und alle zukünftigen Einzeltermine absagen."""

    def post(self, request, recurring_pk):
        from apps.lessons.models import Session as _Session
        from apps.lessons.recurring_models import RecurringSession

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        rs = get_object_or_404(RecurringSession, pk=recurring_pk)
        student = _get_portal_student(portal_user, rs.contract_id)
        if not student:
            return HttpResponseForbidden()

        today = _dt.date.today()
        cancelled = _Session.objects.filter(
            recurring_session=rs,
            date__gte=today,
            status="planned",
        ).update(status="cancelled")

        rs.is_active = False
        rs.save()
        messages.success(request, f"Serientermin beendet. {cancelled} zukünftige Termine abgesagt.")
        return redirect("portal:recurring_manage", student_pk=student.pk)


class PortalDocumentsView(View):
    """Dokumente eines Schülers – auflisten und hochladen."""

    template_name = "portal/documents.html"

    def get(self, request, student_pk):
        from apps.students.models import StudentDocument

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        docs = StudentDocument.objects.filter(student=student)
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "documents": docs,
                "portal_user": portal_user,
            },
        )

    def post(self, request, student_pk):
        from apps.students.models import StudentDocument

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.warning(request, "Keine Datei ausgewählt.")
            return redirect("portal:documents", student_pk=student_pk)

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
            messages.error(
                request,
                "Dateityp nicht erlaubt. Erlaubte Formate: PDF, PNG, JPG, JPEG, DOCX, DOC, XLSX, XLS, TXT.",
            )
            return redirect("portal:documents", student_pk=student_pk)

        if uploaded_file.size > _MAX_UPLOAD_SIZE:
            messages.error(request, "Die Datei ist zu groß. Maximale Dateigröße: 10 MB.")
            return redirect("portal:documents", student_pk=student_pk)

        name = request.POST.get("name", "").strip()
        StudentDocument.objects.create(
            student=student,
            file=uploaded_file,
            name=name,
            uploaded_by_portal_user=portal_user,
            uploaded_by_tutor=False,
        )
        messages.success(request, "Datei erfolgreich hochgeladen.")
        return redirect("portal:documents", student_pk=student_pk)


class PortalDocumentDownloadView(View):
    """Datei herunterladen."""

    def get(self, request, student_pk, doc_pk):
        from django.http import FileResponse

        from apps.students.models import StudentDocument

        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_portal_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        doc = get_object_or_404(StudentDocument, pk=doc_pk, student=student)
        response = FileResponse(
            doc.file.open("rb"), as_attachment=True, filename=doc.display_name()
        )
        return response


class PortalMeetingWaitView(View):
    """
    Warteraum für Portal-Nutzer (Schüler/Elternteil).
    Leitet direkt weiter, wenn ein aktives Meeting existiert.
    """

    template_name = "portal/meeting_wait.html"

    def _check_access(self, request, lesson_pk):
        """Gibt (portal_user, lesson) zurück oder (None, None) bei kein Zugriff."""
        from apps.lessons.models import Lesson

        portal_user = get_portal_user(request)
        if not portal_user:
            return None, None
        lesson = get_object_or_404(Lesson, pk=lesson_pk)
        if portal_user.role == "student":
            link = StudentPortalLink.objects.filter(
                portal_user=portal_user,
                is_active=True,
                contract=lesson.contract,
            ).first()
            if not link:
                return None, None
        elif portal_user.role == "parent":
            has_access = ParentStudentLink.objects.filter(
                parent=portal_user,
                contract=lesson.contract,
            ).exists()
            if not has_access:
                return None, None
        else:
            return None, None
        return portal_user, lesson

    def get(self, request, lesson_pk):

        portal_user, lesson = self._check_access(request, lesson_pk)
        if portal_user is None:
            from django.urls import reverse

            login_url = reverse("portal:login")
            next_url = request.path
            if url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(f"{login_url}?next={next_url}")
            return redirect(login_url)

        # Wenn Meeting bereits aktiv → direkt weiterleiten
        try:
            room = lesson.meeting_room
            if room.is_active:
                return redirect("meeting:room", token=room.token)
        except Exception:  # noqa: S110 – kein MeetingRoom vorhanden
            pass

        return render(
            request,
            self.template_name,
            {
                "lesson": lesson,
                "portal_user": portal_user,
                "status_url": f"/portal/meeting/{lesson_pk}/status/",
                "room_url_base": "/meetings/",
            },
        )


class PortalMeetingStatusView(View):
    """JSON-Endpunkt: Ist ein Meeting aktiv? (für Polling im Warteraum)"""

    def get(self, request, lesson_pk):
        from django.http import JsonResponse

        from apps.lessons.models import Lesson

        portal_user = get_portal_user(request)
        if not portal_user:
            return JsonResponse({"active": False})
        lesson = get_object_or_404(Lesson, pk=lesson_pk)

        # Zugangsprüfung
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

        if not ok:
            return JsonResponse({"active": False})

        try:
            room = lesson.meeting_room
            if room.is_active:
                return JsonResponse({"active": True, "token": str(room.token)})
        except Exception:  # noqa: S110 – kein MeetingRoom vorhanden
            pass

        return JsonResponse({"active": False})


class PortalCalendarView(View):
    """Month calendar for portal users (student and parent)."""

    template_name = "portal/calendar.html"

    def _get_student(self, portal_user, student_pk=None):
        if portal_user.role == "student":
            link = StudentPortalLink.objects.filter(portal_user=portal_user, is_active=True).first()
            if not link:
                return None
            return link.contract
        else:
            if not student_pk:
                return None
            link = ParentStudentLink.objects.filter(
                parent=portal_user, contract_id=student_pk
            ).first()
            return link.contract if link else None

    def get(self, request, student_pk=None):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")

        student = self._get_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()

        now = timezone.now()
        try:
            year = int(request.GET.get("year", now.year))
            month = int(request.GET.get("month", now.month))
        except (ValueError, TypeError):
            year, month = now.year, now.month

        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1

        start_date = _dt.date(year, month, 1)
        if month == 12:
            end_date = _dt.date(year + 1, 1, 1)
        else:
            end_date = _dt.date(year, month + 1, 1)

        lessons = _Lesson.objects.filter(
            contract=student, date__gte=start_date, date__lt=end_date
        ).order_by("date", "start_time")

        lessons_by_date = {}
        for lesson in lessons:
            lessons_by_date.setdefault(lesson.date, []).append(lesson)

        cal = _monthcalendar(year, month)
        today = timezone.localdate()
        weeks = []
        for week in cal:
            week_days = []
            for day in week:
                if day == 0:
                    week_days.append(None)
                else:
                    d = _dt.date(year, month, day)
                    week_days.append(
                        {
                            "date": d,
                            "is_today": d == today,
                            "is_past": d < today,
                            "lessons": lessons_by_date.get(d, []),
                        }
                    )
            weeks.append(week_days)

        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1

        month_names = [
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember",
        ]

        context = {
            "student": student,
            "portal_user": portal_user,
            "weeks": weeks,
            "year": year,
            "month": month,
            "month_label": month_names[month - 1],
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "today": today,
            "weekday_names": [
                "Montag",
                "Dienstag",
                "Mittwoch",
                "Donnerstag",
                "Freitag",
                "Samstag",
                "Sonntag",
            ],
        }

        if portal_user.role == "parent":
            context["student_pk"] = student_pk

        return render(request, self.template_name, context)


class PortalWeekView(View):
    """Wochenansicht für Portal-Nutzer (Schüler und Eltern)."""

    template_name = "portal/calendar_week.html"

    def _get_student(self, portal_user, student_pk=None):
        if portal_user.role == "student":
            link = StudentPortalLink.objects.filter(portal_user=portal_user, is_active=True).first()
            if not link:
                return None
            return link.contract
        else:
            if not student_pk:
                return None
            link = ParentStudentLink.objects.filter(
                parent=portal_user, contract_id=student_pk
            ).first()
            return link.contract if link else None

    def get(self, request, student_pk=None):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")

        student = self._get_student(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()

        now = timezone.now()
        try:
            year = int(request.GET.get("year", now.year))
            month = int(request.GET.get("month", now.month))
            day = int(request.GET.get("day", now.day))
        except (ValueError, TypeError):
            year, month, day = now.year, now.month, now.day

        current_date = _dt.date(year, month, day)
        # Montag der aktuellen Woche
        week_start = current_date - _dt.timedelta(days=current_date.weekday())
        week_end = week_start + _dt.timedelta(days=6)

        lessons = _Lesson.objects.filter(
            contract=student,
            date__gte=week_start,
            date__lte=week_end,
        ).order_by("date", "start_time")

        lessons_by_date = {}
        for lesson in lessons:
            lessons_by_date.setdefault(lesson.date, []).append(lesson)

        weekday_names = [
            "Montag",
            "Dienstag",
            "Mittwoch",
            "Donnerstag",
            "Freitag",
            "Samstag",
            "Sonntag",
        ]
        weekday_names_short = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        today = timezone.localdate()
        weekdays = []
        for i in range(7):
            d = week_start + _dt.timedelta(days=i)
            weekdays.append(
                {
                    "date": d,
                    "name": weekday_names[i],
                    "name_short": weekday_names_short[i],
                    "is_today": d == today,
                    "is_past": d < today,
                    "lessons": lessons_by_date.get(d, []),
                }
            )

        prev_week = week_start - _dt.timedelta(days=7)
        next_week = week_start + _dt.timedelta(days=7)

        context = {
            "student": student,
            "portal_user": portal_user,
            "weekdays": weekdays,
            "week_start": week_start,
            "week_end": week_end,
            "prev_week": prev_week,
            "next_week": next_week,
            "today": today,
            "hours": list(range(7, 22)),
        }

        if portal_user.role == "parent":
            context["student_pk"] = student_pk

        return render(request, self.template_name, context)
