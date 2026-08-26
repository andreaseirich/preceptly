import datetime as _dt
import logging
import os
import secrets
import uuid
from calendar import monthcalendar as _monthcalendar

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import localtime as _localtime
from django.utils.translation import gettext_lazy as _
from django.views import View
from django_ratelimit.decorators import ratelimit

from apps.core.upload_validation import sanitize_doc_name, validate_file_magic
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
_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


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
        from django.contrib.auth.hashers import check_password as _check_password

        _DUMMY_HASH = "pbkdf2_sha256$600000$dummy$dummyhashfortimingnoop="

        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()
        error = None

        # E-Mail-basiertes Login: Django-User über portal_profile suchen
        try:
            from django.contrib.auth import get_user_model as _get_user_model

            _User = _get_user_model()
            django_user = _User.objects.get(email__iexact=email, portal_profile__isnull=False)
        except _User.DoesNotExist:
            # Fallback: E-Mail liegt am Vertrag, nicht am Django-User (Legacy/Sync-Problem)
            # Suche zuerst mit is_active=True; falls nicht gefunden auch ohne (nach Resend-Invite)
            try:
                from apps.portal.models import StudentPortalLink as _SPL

                try:
                    spl = _SPL.objects.select_related("portal_user__user").get(
                        contract__email__iexact=email,
                        is_active=True,
                    )
                except _SPL.DoesNotExist:
                    # Nach Resend-Invite ist is_active=False; Passwort ist aber noch gültig
                    spl = _SPL.objects.select_related("portal_user__user").get(
                        contract__email__iexact=email,
                    )
                django_user = spl.portal_user.user
                # Selbstheilung: E-Mail am Django-User auf aktuelle Contract-E-Mail setzen
                contract_email = spl.contract.email or ""
                if contract_email and contract_email.lower() != (django_user.email or "").lower():
                    old_email = django_user.email
                    django_user.email = contract_email
                    django_user.save(update_fields=["email"])
                    logger.info(
                        "Portal-Login: E-Mail für User pk=%s aktualisiert (%r → %r)",
                        django_user.pk,
                        old_email,
                        contract_email,
                    )
                elif not django_user.email:
                    django_user.email = email
                    django_user.save(update_fields=["email"])
                    logger.info("Portal-Login: E-Mail für User pk=%s nachgetragen", django_user.pk)
            except (_SPL.DoesNotExist, _SPL.MultipleObjectsReturned):
                logger.warning(
                    "Portal-Login fehlgeschlagen: kein Nutzer mit email=%r und portal_profile",
                    email,
                )
                _check_password("dummy", _DUMMY_HASH)
                return render(request, self.template_name, {"error": _("Ungültige Zugangsdaten.")})
        except _User.MultipleObjectsReturned:
            logger.warning(
                "Portal-Login fehlgeschlagen: mehrere Nutzer mit email=%r gefunden", email
            )
            _check_password("dummy", _DUMMY_HASH)
            return render(request, self.template_name, {"error": _("Ungültige Zugangsdaten.")})

        if not django_user.is_active:
            logger.warning(
                "Portal-Login fehlgeschlagen: Nutzer pk=%s (email=%r) ist nicht aktiv",
                django_user.pk,
                email,
            )
            _check_password("dummy", _DUMMY_HASH)
            return render(request, self.template_name, {"error": _("Ungültige Zugangsdaten.")})
        elif not django_user.check_password(password):
            logger.warning(
                "Portal-Login fehlgeschlagen: Passwort-Check fehlgeschlagen für pk=%s (email=%r)",
                django_user.pk,
                email,
            )
            _check_password("dummy", _DUMMY_HASH)
            return render(request, self.template_name, {"error": _("Ungültige Zugangsdaten.")})

        try:
            portal_user = PortalUser.objects.get(user=django_user)
        except PortalUser.DoesNotExist:
            _check_password("dummy", _DUMMY_HASH)
            error = _("Ungültige Zugangsdaten.")
            return render(request, self.template_name, {"error": error})

        # Session-Fixation-Schutz: Session-Key vor dem Setzen rotieren
        request.session.cycle_key()
        request.session["portal_user_id"] = portal_user.pk

        next_url = request.POST.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("portal:home")


class PortalLogoutView(View):
    def post(self, request):
        request.session.flush()
        return redirect("portal:login")


class PortalDispatchView(View):
    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        # Genau ein aktives Kind: direkte Ansicht. 0 oder mehrere: Familien-Übersicht.
        if _get_default_portal_student(portal_user):
            return redirect("portal:student_home")
        return redirect("portal:parent_home")


class StudentHomeView(View):
    template_name = "portal/student_home.html"

    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = _get_default_portal_student(portal_user)
        if not student:
            return redirect("portal:parent_home")
        from apps.lessons.models import Lesson

        today = _dt.date.today()
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
        if not portal_user:
            return redirect("portal:login")
        student = _get_default_portal_student(portal_user)
        if not student:
            return redirect("portal:parent_home")
        from apps.lessons.models import Lesson

        lessons = Lesson.objects.filter(
            contract=student,
        ).order_by("-date", "-start_time")
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "lessons": lessons,
                "portal_user": portal_user,
            },
        )


class ParentHomeView(View):
    template_name = "portal/parent_home.html"

    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        if _get_default_portal_student(portal_user):
            return redirect("portal:student_home")
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
                    "contract__portal_messages",
                    filter=Q(contract__portal_messages__read_by_portal=False),
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
        if not portal_user:
            return redirect("portal:login")
        link = get_object_or_404(
            ParentStudentLink, parent=portal_user, contract_id=student_pk, is_active=True
        )
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
        return _get_portal_student(portal_user, student_pk)

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

        cutoff = timezone.now() - timedelta(days=7)
        # Tokens die älter als 7 Tage sind, werden abgelehnt.
        # Fallback: noch nicht aktivierte Einladungen ohne Timestamp (Legacy) werden akzeptiert.
        valid = Q(invite_token_created_at__gte=cutoff) | Q(
            invite_token_created_at__isnull=True, is_active=False
        )
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
            return render(
                request,
                self.template_name,
                {
                    "token": token,
                    "error_expired": True,
                },
            )
        if link.is_active:
            return redirect("portal:login")
        return render(request, self.template_name, {"token": token, "student": link.contract})

    def post(self, request, token):
        link, portal_user = self._get_link(token)
        if link is None:
            return render(
                request,
                self.template_name,
                {
                    "token": token,
                    "error_expired": True,
                },
            )
        if link.is_active:
            return redirect("portal:login")
        password = request.POST.get("password", "").strip()
        password2 = request.POST.get("password_confirm", "").strip()
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
        try:
            validate_password(password, portal_user.user)
        except ValidationError as e:
            return render(
                request,
                self.template_name,
                {
                    "token": token,
                    "student": link.contract,
                    "error": " ".join(e.messages),
                },
            )
        # E-Mail aus Vertrag übernehmen, falls Django-User sie noch nicht hat (Sync-Schutz)
        if not portal_user.user.email and hasattr(link, "contract") and link.contract.email:
            portal_user.user.email = link.contract.email
        portal_user.user.set_password(password)
        portal_user.user.save()
        link.is_active = True
        # Token nach erfolgreicher Aktivierung invalidieren
        link.invite_token = uuid.uuid4().hex
        link.invite_token_created_at = None
        link.save()
        # Session-Fixation-Schutz: Session-Key vor dem Setzen rotieren
        request.session.cycle_key()
        request.session["portal_user_id"] = portal_user.pk
        return redirect("portal:home")


class PortalPasswordResetRequestView(View):
    template_name = "portal/password_reset.html"

    def get(self, request):
        return render(request, self.template_name)

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        email = request.POST.get("email", "").strip().lower()
        try:
            user = User.objects.get(email__iexact=email, portal_profile__isnull=False)
            portal_user = PortalUser.objects.get(user=user)
            # Reuse invite_token mechanism for reset (irrelevant which linked
            # contract; reset_token identifies the account, not a specific child)
            link = ParentStudentLink.objects.filter(parent=portal_user).first()
            if link:
                link.reset_token = secrets.token_urlsafe(32)
                link.reset_token_created_at = timezone.now()
                link.save(update_fields=["reset_token", "reset_token_created_at"])
                # Get recipient email: user.email if available, else student.email
                recipient = user.email or link.contract.email
                if recipient:
                    from django.conf import settings
                    from django.core.mail import send_mail
                    from django.template.loader import render_to_string

                    site_url = getattr(settings, "SITE_URL", "https://preceptly.de")
                    reset_url = f"{site_url}/portal/password-reset/confirm/{link.reset_token}/"
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
            User.MultipleObjectsReturned,
            PortalUser.DoesNotExist,
            StudentPortalLink.DoesNotExist,
            ParentStudentLink.DoesNotExist,
        ):
            pass  # Existenz von Accounts nicht preisgeben
        return render(request, self.template_name, {"sent": True})


class PortalPasswordResetConfirmView(View):
    template_name = "portal/password_reset_confirm.html"

    def _get_link(self, token):
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=7)
        link = StudentPortalLink.objects.filter(
            reset_token=token, reset_token_created_at__gte=cutoff
        ).first()
        if link:
            return link, link.portal_user
        link = ParentStudentLink.objects.filter(
            reset_token=token, reset_token_created_at__gte=cutoff
        ).first()
        if link:
            return link, link.parent
        return None, None

    def get(self, request, token):
        link, portal_user = self._get_link(token)
        if link is None:
            return render(request, self.template_name, {"token": token, "error_expired": True})
        return render(request, self.template_name, {"token": token, "student": link.contract})

    def post(self, request, token):
        link, portal_user = self._get_link(token)
        if link is None:
            return render(request, self.template_name, {"token": token, "error_expired": True})
        password = request.POST.get("password", "").strip()
        password2 = request.POST.get("password_confirm", "").strip()
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
        try:
            validate_password(password, portal_user.user)
        except ValidationError as e:
            return render(
                request,
                self.template_name,
                {
                    "token": token,
                    "student": link.contract,
                    "error": " ".join(e.messages),
                },
            )
        portal_user.user.set_password(password)
        portal_user.user.save()
        link.reset_token = None
        link.reset_token_created_at = None
        link.save(update_fields=["reset_token", "reset_token_created_at"])
        request.session.cycle_key()
        request.session["portal_user_id"] = portal_user.pk
        return redirect("portal:home")


class StudentLessonDetailView(View):
    template_name = "portal/student_lesson_detail.html"

    def get(self, request, pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")

        from apps.lessons.models import Lesson

        # Zugriff auf Stunden aller aktiv verknüpften Kinder (auch im Ein-Kind-Fall)
        contract_ids = list(
            ParentStudentLink.objects.filter(parent=portal_user, is_active=True).values_list(
                "contract_id", flat=True
            )
        )
        lesson = get_object_or_404(Lesson, pk=pk, contract_id__in=contract_ids)
        student = lesson.contract

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
    """Gibt den Vertrag zurück, falls portal_user Zugriff darauf hat, sonst None."""
    link = ParentStudentLink.objects.filter(
        parent=portal_user, contract_id=student_pk, is_active=True
    ).first()
    if not link or link.contract.user_id != portal_user.tutor_id:
        return None
    return link.contract


def _get_default_portal_student(portal_user):
    """Vertrag bei genau einem aktiven Kind (Ein-Kind-Fall, implizite Auswahl).

    Bei 0 oder 2+ Kindern gibt es keine eindeutige Standardauswahl —
    der Aufrufer muss dann explizit über student_pk auswählen (Familien-
    Übersicht)."""
    links = list(ParentStudentLink.objects.filter(parent=portal_user, is_active=True)[:2])
    if len(links) != 1:
        return None
    contract = links[0].contract
    if contract.user_id != portal_user.tutor_id:
        return None
    return contract


def _portal_redirect_after_action(portal_user, student):
    """Zurück zur Einzelansicht (Ein-Kind-Fall) oder zur Kind-Detailseite
    (Familien-Übersicht), je nachdem wie viele Kinder verknüpft sind."""
    default = _get_default_portal_student(portal_user)
    if default and default.pk == student.pk:
        return redirect("portal:student_lessons")
    return redirect("portal:parent_student_detail", student_pk=student.pk)


def _get_active_contract(student):
    """Gibt den Vertrag zurück falls er aktiv ist, sonst None.

    Im Portal-Kontext ist 'student' bereits ein Contract-Objekt.
    """
    today = _dt.date.today()
    if not student.is_active:
        return None
    end_date = getattr(student, "end_date", None)
    if end_date and end_date < today:
        return None
    return student


def _get_busy_slots(tutor, date):
    from apps.blocked_times.models import BlockedTime
    from apps.lessons.models import Session as _Session

    busy = []
    sessions = _Session.objects.filter(
        contract__user=tutor,
        date=date,
        status__in=["planned", "taught", "paid"],
    )
    for s in sessions:
        s_start = _dt.datetime.combine(date, s.start_time)
        s_end = s_start + _dt.timedelta(minutes=s.duration_minutes)
        busy.append((s.start_time, s_end.time()))
    blocked_times = BlockedTime.objects.filter(
        user=tutor,
        start_datetime__date__lte=date,
        end_datetime__date__gte=date,
    )
    for bt in blocked_times:
        clamped_start = max(
            _localtime(bt.start_datetime).replace(tzinfo=None),
            _dt.datetime.combine(date, _dt.time(0, 0)),
        )
        clamped_end = min(
            _localtime(bt.end_datetime).replace(tzinfo=None),
            _dt.datetime.combine(date, _dt.time(23, 59)),
        )
        if clamped_start < clamped_end:
            busy.append((clamped_start.time(), clamped_end.time()))
    return busy


def _get_available_slots(tutor, date, duration_minutes=60, slot_interval=30):
    """Gibt sortierte Liste freier Startzeiten (HH:MM) zurück."""
    from apps.blocked_times.models import BlockedTime
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

    blocked_times = BlockedTime.objects.filter(
        user=tutor,
        start_datetime__date__lte=date,
        end_datetime__date__gte=date,
    )
    day_start_dt = _dt.datetime.combine(date, _dt.time(0, 0))
    day_end_dt = _dt.datetime.combine(date, _dt.time(23, 59))
    for bt in blocked_times:
        bt_start = _localtime(bt.start_datetime).replace(tzinfo=None)
        bt_end = _localtime(bt.end_datetime).replace(tzinfo=None)
        clamped_start = max(bt_start, day_start_dt)
        clamped_end = min(bt_end, day_end_dt)
        if clamped_start < clamped_end:
            busy.append((clamped_start.time(), clamped_end.time()))

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
        busy = _get_busy_slots(student.user, date)
        busy_data = [{"start": s.strftime("%H:%M"), "end": e.strftime("%H:%M")} for s, e in busy]
        tutor_tz = (
            getattr(getattr(student.user, "profile", None), "timezone", "Europe/Berlin")
            or "Europe/Berlin"
        )
        return JsonResponse(
            {
                "slots": slots,
                "busy_slots": busy_data,
                "duration_minutes": duration,
                "tutor_timezone": tutor_tz,
            }
        )


class PortalBookingView(View):
    """Terminbuchung aus dem Portal."""

    template_name = "portal/book.html"

    def _render(self, request, student, contract, error=None, success=None):
        today = _dt.date.today()
        now = timezone.now()
        try:
            year = int(request.GET.get("year", now.year))
            month = int(request.GET.get("month", now.month))
            day = int(request.GET.get("day", now.day))
        except (ValueError, TypeError):
            year, month, day = now.year, now.month, now.day
        context = {
            "student": student,
            "contract": contract,
            "error": error,
            "success": success,
            "portal_user": get_portal_user(request),
        }
        context.update(_build_week_calendar(student, year, month, day))
        context["today"] = today.isoformat()
        return render(request, self.template_name, context)

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

        # BlockedTime-Konflikt-Prüfung
        from apps.blocked_times.models import BlockedTime

        day_start_dt = _dt.datetime.combine(session_date, _dt.time(0, 0))
        day_end_dt = _dt.datetime.combine(session_date, _dt.time(23, 59, 59))
        blocked_times = BlockedTime.objects.filter(
            user=student.user,
            start_datetime__date__lte=session_date,
            end_datetime__date__gte=session_date,
        )
        for bt in blocked_times:
            bt_start = max(_localtime(bt.start_datetime).replace(tzinfo=None), day_start_dt)
            bt_end = min(_localtime(bt.end_datetime).replace(tzinfo=None), day_end_dt)
            if start_dt < bt_end and end_dt > bt_start:
                return self._render(
                    request,
                    student,
                    contract,
                    error="Diese Zeit ist durch eine Blockzeit belegt.",
                )

        session = _Session.objects.create(
            contract=contract,
            date=session_date,
            start_time=session_time,
            duration_minutes=duration,
            status="planned",
            notes=topic or None,
            created_via="portal_booking",
        )
        try:
            from apps.portal.email_service import send_booking_notification_portal

            send_booking_notification_portal(session, student.user)
        except Exception:
            import logging as _logging

            _logging.getLogger(__name__).exception("Portal-Buchungsbenachrichtigung fehlgeschlagen")
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

        # IDOR-Schutz: Ownership-Prüfung über _get_portal_student,
        # welches die Zugriffsrechte des portal_user auf den contract verifiziert.
        student = _get_portal_student(portal_user, session.contract_id)
        if not student:
            return HttpResponseForbidden()

        # Zusätzliche Konsistenzprüfung: Session muss wirklich zum geprüften Contract gehören
        if session.contract_id != student.pk:
            return HttpResponseForbidden()

        # Tutor-Konsistenz: contract.user muss zum portal_user.tutor passen
        if session.contract.user_id != portal_user.tutor_id:
            return HttpResponseForbidden()

        if session.status != "planned":
            messages.warning(request, "Nur geplante Termine können abgesagt werden.")
        else:
            date_str = session.date.strftime("%d.%m.%Y")
            session.delete()
            messages.success(request, f"Termin am {date_str} wurde abgesagt.")

        # Zurück zur richtigen Übersicht
        return _portal_redirect_after_action(portal_user, student)


class PortalSessionRescheduleView(View):
    """Termin verschieben."""

    template_name = "portal/reschedule.html"

    def _get_session_and_student(self, request, session_pk):
        from apps.lessons.models import Session as _Session

        portal_user = get_portal_user(request)
        if not portal_user:
            return None, None, None
        session = get_object_or_404(_Session, pk=session_pk)

        # IDOR-Schutz: Ownership-Prüfung über _get_portal_student
        student = _get_portal_student(portal_user, session.contract_id)
        if not student:
            return portal_user, session, None

        # Zusätzliche Konsistenzprüfungen
        if session.contract_id != student.pk:
            return portal_user, session, None
        if session.contract.user_id != portal_user.tutor_id:
            return portal_user, session, None

        return portal_user, session, student

    def _render(self, request, session, student, portal_user, error=None):
        today = _dt.date.today()
        now = timezone.now()
        try:
            year = int(request.GET.get("year", now.year))
            month = int(request.GET.get("month", now.month))
            day = int(request.GET.get("day", now.day))
        except (ValueError, TypeError):
            year, month, day = now.year, now.month, now.day
        context = {
            "session": session,
            "student": student,
            "portal_user": portal_user,
            "error": error,
        }
        context.update(_build_week_calendar(student, year, month, day))
        context["today"] = today.isoformat()
        return render(request, self.template_name, context)

    def get(self, request, session_pk):
        portal_user, session, student = self._get_session_and_student(request, session_pk)
        if not portal_user:
            return redirect("portal:login")
        if not student:
            return HttpResponseForbidden()
        return self._render(request, session, student, portal_user)

    def post(self, request, session_pk):
        from apps.lessons.models import Session as _Session

        portal_user, session, student = self._get_session_and_student(request, session_pk)
        if not portal_user:
            return redirect("portal:login")
        if not student:
            return HttpResponseForbidden()
        if session.status != "planned":
            messages.warning(request, "Nur geplante Termine können verschoben werden.")
            return _portal_redirect_after_action(portal_user, student)

        date_str = request.POST.get("date", "").strip()
        time_str = request.POST.get("start_time", "").strip()
        try:
            new_date = _dt.date.fromisoformat(date_str)
            new_time = _dt.time.fromisoformat(time_str)
        except ValueError:
            return self._render(
                request, session, student, portal_user, error="Ungültiges Datum oder Uhrzeit."
            )

        if new_date < _dt.date.today():
            return self._render(
                request,
                session,
                student,
                portal_user,
                error="Das Datum liegt in der Vergangenheit.",
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
                return self._render(
                    request,
                    session,
                    student,
                    portal_user,
                    error=f"Zeitkonflikt mit Termin um {ex.start_time.strftime('%H:%M')} Uhr.",
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
        return _portal_redirect_after_action(portal_user, student)


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
        deleted_count, _ = _Session.objects.filter(
            recurring_session=rs,
            date__gte=today,
            status="planned",
        ).delete()

        rs.is_active = False
        rs.save()
        messages.success(
            request, f"Serientermin beendet. {deleted_count} zukünftige Termine gelöscht."
        )
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
            messages.error(request, "Die Datei ist zu groß. Maximale Dateigröße: 50 MB.")
            return redirect("portal:documents", student_pk=student_pk)

        if not validate_file_magic(uploaded_file, ext):
            messages.error(
                request, "Dateityp nicht erlaubt (Inhalt stimmt nicht mit Dateiendung überein)."
            )
            return redirect("portal:documents", student_pk=student_pk)

        name = sanitize_doc_name(request.POST.get("name", "").strip() or uploaded_file.name)
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
        if not doc.file_exists:
            from django.http import Http404

            raise Http404
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
        has_access = ParentStudentLink.objects.filter(
            parent=portal_user,
            contract=lesson.contract,
            is_active=True,
        ).exists()
        if not has_access:
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
        ok = ParentStudentLink.objects.filter(
            parent=portal_user, contract=lesson.contract, is_active=True
        ).exists()

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
        if student_pk:
            return _get_portal_student(portal_user, student_pk)
        return _get_default_portal_student(portal_user)

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

        # Alle belegten Zeiten des Tutors fuer den Monat (anonymisiert)
        import datetime as _datetime_mod

        from apps.blocked_times.models import BlockedTime as _BT
        from apps.lessons.models import Session as _AllSessions

        tutor = student.user
        all_sessions = _AllSessions.objects.filter(
            contract__user=tutor,
            date__gte=start_date,
            date__lt=end_date,
            status__in=["planned", "taught", "paid"],
        )
        busy_by_date = {}
        for s in all_sessions:
            entry = {
                "start": s.start_time.strftime("%H:%M"),
                "end": (
                    (
                        _datetime_mod.datetime.combine(s.date, s.start_time)
                        + _datetime_mod.timedelta(minutes=s.duration_minutes)
                    ).time()
                ).strftime("%H:%M"),
                "is_own": s.contract == student,
            }
            busy_by_date.setdefault(s.date, []).append(entry)
        start_aware = __import__("django.utils.timezone", fromlist=["make_aware"]).make_aware(
            _datetime_mod.datetime.combine(start_date, _datetime_mod.time.min)
        )
        end_aware = __import__("django.utils.timezone", fromlist=["make_aware"]).make_aware(
            _datetime_mod.datetime.combine(end_date, _datetime_mod.time.min)
        )
        blocked = _BT.objects.filter(
            user=tutor, start_datetime__lt=end_aware, end_datetime__gt=start_aware
        )
        for bt in blocked:
            bt_start_local = _localtime(bt.start_datetime)
            bt_end_local = _localtime(bt.end_datetime)
            bt_date = bt_start_local.date()
            while (
                bt_date < bt_end_local.date() + _datetime_mod.timedelta(days=1)
                and bt_date < end_date
            ):
                if bt_date >= start_date:
                    entry = {
                        "start": bt_start_local.strftime("%H:%M")
                        if bt_date == bt_start_local.date()
                        else "00:00",
                        "end": bt_end_local.strftime("%H:%M")
                        if bt_date == bt_end_local.date()
                        else "23:59",
                        "is_own": False,
                    }
                    busy_by_date.setdefault(bt_date, []).append(entry)
                bt_date += _datetime_mod.timedelta(days=1)

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
                            "busy": busy_by_date.get(d, []),
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
            "busy_by_date": busy_by_date,
            "tutor_timezone": getattr(
                getattr(student.user, "profile", None), "timezone", "Europe/Berlin"
            )
            or "Europe/Berlin",
        }

        if student_pk:
            context["student_pk"] = student_pk

        return render(request, self.template_name, context)


def _build_week_calendar(student, year, month, day):
    """Berechnet Wochenkalender-Daten (Stunden, Belegtzeiten) für einen Vertrag.

    Wird sowohl von der Kalender-Wochenansicht als auch von der
    Buchungs-/Verschiebungs-Ansicht verwendet, damit Schüler beim Buchen
    dieselbe Frei/Belegt-Übersicht sehen wie im reinen Kalender.
    """
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
    import datetime as _dt_mod

    from django.utils.timezone import make_aware as _make_aware2

    from apps.blocked_times.models import BlockedTime as _BT2
    from apps.lessons.models import Session as _AllSess2

    tutor = student.user
    all_sessions_week = _AllSess2.objects.filter(
        contract__user=tutor,
        date__gte=week_start,
        date__lte=week_end,
        status__in=["planned", "taught", "paid"],
    )
    busy_by_date_week = {}
    for _s in all_sessions_week:
        _entry = {
            "start": _s.start_time.strftime("%H:%M"),
            "end": (
                (
                    _dt_mod.datetime.combine(_s.date, _s.start_time)
                    + _dt_mod.timedelta(minutes=_s.duration_minutes)
                ).time()
            ).strftime("%H:%M"),
            "start_hour": _s.start_time.hour,
            "start_min": _s.start_time.minute,
            "duration": _s.duration_minutes,
            "is_own": _s.contract == student,
        }
        busy_by_date_week.setdefault(_s.date, []).append(_entry)
    _w_start_aware = _make_aware2(_dt_mod.datetime.combine(week_start, _dt_mod.time.min))
    _w_end_aware = _make_aware2(
        _dt_mod.datetime.combine(week_end + _dt_mod.timedelta(days=1), _dt_mod.time.min)
    )
    _blocked_week = _BT2.objects.filter(
        user=tutor, start_datetime__lt=_w_end_aware, end_datetime__gt=_w_start_aware
    )
    for _bt in _blocked_week:
        _bt_start_local = _localtime(_bt.start_datetime).replace(tzinfo=None)
        _bt_end_local = _localtime(_bt.end_datetime).replace(tzinfo=None)
        _bt_date = _bt_start_local.date()
        while _bt_date <= _bt_end_local.date() and _bt_date <= week_end:
            if _bt_date >= week_start:
                _bt_start_t = (
                    _bt_start_local
                    if _bt_date == _bt_start_local.date()
                    else _dt_mod.datetime.combine(_bt_date, _dt_mod.time.min)
                )
                _bt_end_t = (
                    _bt_end_local
                    if _bt_date == _bt_end_local.date()
                    else _dt_mod.datetime.combine(_bt_date, _dt_mod.time(23, 59))
                )
                _entry = {
                    "start": _bt_start_t.strftime("%H:%M"),
                    "end": _bt_end_t.strftime("%H:%M"),
                    "start_hour": _bt_start_t.hour,
                    "start_min": _bt_start_t.minute,
                    "duration": int((_bt_end_t - _bt_start_t).total_seconds() / 60),
                    "is_own": False,
                }
                busy_by_date_week.setdefault(_bt_date, []).append(_entry)
            _bt_date += _dt_mod.timedelta(days=1)

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
                "busy": busy_by_date_week.get(d, []),
            }
        )

    prev_week = week_start - _dt.timedelta(days=7)
    next_week = week_start + _dt.timedelta(days=7)

    return {
        "weekdays": weekdays,
        "week_start": week_start,
        "week_end": week_end,
        "prev_week": prev_week,
        "next_week": next_week,
        "today": today,
        "hours": list(range(7, 22)),
        "tutor_timezone": getattr(
            getattr(student.user, "profile", None), "timezone", "Europe/Berlin"
        )
        or "Europe/Berlin",
    }


class PortalWeekView(View):
    """Wochenansicht für Portal-Nutzer (Schüler und Eltern)."""

    template_name = "portal/calendar_week.html"

    def _get_student(self, portal_user, student_pk=None):
        if student_pk:
            return _get_portal_student(portal_user, student_pk)
        return _get_default_portal_student(portal_user)

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

        context = {
            "student": student,
            "portal_user": portal_user,
            **_build_week_calendar(student, year, month, day),
        }

        if student_pk:
            context["student_pk"] = student_pk

        return render(request, self.template_name, context)


class PortalFAQView(View):
    """FAQ-Seite für Portal-Nutzer."""

    template_name = "portal/faq.html"

    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        return render(request, self.template_name, {"portal_user": portal_user})


class PortalProfileEditView(View):
    """Schüler/Elternteil kann eigene Kontaktdaten und Passwort ändern."""

    template_name = "portal/profile_edit.html"

    def _get_contract(self, portal_user):
        """Gibt den primären Vertrag des Portal-Nutzers zurück (das eine
        Kind im Ein-Kind-Fall, sonst das zuerst verknüpfte Kind)."""
        link = (
            ParentStudentLink.objects.select_related("contract")
            .filter(parent=portal_user, is_active=True)
            .first()
        )
        return link.contract if link else None

    def get(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        contract = self._get_contract(portal_user)
        from apps.core.models import NotificationPreference

        notif_pref, _created = NotificationPreference.objects.get_or_create(user=portal_user.user)
        return render(
            request,
            self.template_name,
            {
                "portal_user": portal_user,
                "contract": contract,
                "notif_pref": notif_pref,
            },
        )

    def post(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        contract = self._get_contract(portal_user)
        django_user = portal_user.user

        errors = []
        success_msgs = []

        action = request.POST.get("action", "")

        if action == "contact":
            new_email = request.POST.get("email", "").strip().lower()
            new_phone = request.POST.get("phone", "").strip()

            if new_email and new_email != (django_user.email or "").lower():
                from django.contrib.auth import get_user_model as _gum

                from apps.contracts.models import Contract as _Contract

                _User = _gum()
                duplicate_user = (
                    _User.objects.filter(email__iexact=new_email, portal_profile__isnull=False)
                    .exclude(pk=django_user.pk)
                    .exists()
                )
                duplicate_contract = (
                    _Contract.objects.filter(email__iexact=new_email, parent_links__isnull=False)
                    .exclude(pk=contract.pk if contract else None)
                    .exists()
                )
                if duplicate_user or duplicate_contract:
                    errors.append(
                        "Diese E-Mail-Adresse wird bereits von einem anderen Konto verwendet."
                    )
                else:
                    django_user.email = new_email
                    django_user.save(update_fields=["email"])
                    if contract:
                        contract.email = new_email
                        contract.save(update_fields=["email", "updated_at"])
                    success_msgs.append("E-Mail-Adresse aktualisiert.")

            if contract and new_phone != (contract.phone or ""):
                contract.phone = new_phone or None
                contract.save(update_fields=["phone", "updated_at"])
                success_msgs.append("Telefonnummer aktualisiert.")

        elif action == "password":
            current_pw = request.POST.get("current_password", "")
            new_pw = request.POST.get("new_password", "")
            new_pw2 = request.POST.get("new_password_confirm", "")

            if not django_user.check_password(current_pw):
                errors.append("Das aktuelle Passwort ist falsch.")
            elif new_pw != new_pw2:
                errors.append("Die neuen Passwörter stimmen nicht überein.")
            else:
                try:
                    validate_password(new_pw, django_user)
                except ValidationError as e:
                    errors.extend(e.messages)
                else:
                    django_user.set_password(new_pw)
                    django_user.save()
                    request.session.cycle_key()
                    request.session["portal_user_id"] = portal_user.pk
                    success_msgs.append("Passwort erfolgreich geändert.")

        elif action == "notifications":
            from apps.core.models import NotificationPreference

            notif_pref, _created = NotificationPreference.objects.get_or_create(user=django_user)
            notif_pref.notify_login_reminder_email = bool(
                request.POST.get("notify_login_reminder_email")
            )
            notif_pref.notify_login_reminder_push = bool(
                request.POST.get("notify_login_reminder_push")
            )
            notif_pref.save(
                update_fields=[
                    "notify_login_reminder_email",
                    "notify_login_reminder_push",
                    "updated_at",
                ]
            )
            success_msgs.append("Benachrichtigungseinstellungen gespeichert.")

        from apps.core.models import NotificationPreference as _NotifPref

        notif_pref, _created = _NotifPref.objects.get_or_create(user=django_user)

        return render(
            request,
            self.template_name,
            {
                "portal_user": portal_user,
                "contract": contract,
                "errors": errors,
                "success_msgs": success_msgs,
                "notif_pref": notif_pref,
            },
        )


class PortalPushSubscribeView(View):
    """POST body: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}} - registers
    a Web Push subscription for the logged-in portal user (student/parent)."""

    def post(self, request):
        import json

        from django.http import HttpResponseBadRequest

        from apps.core.push_service import save_push_subscription

        portal_user = get_portal_user(request)
        if not portal_user:
            return HttpResponseForbidden("Not logged in")

        try:
            data = json.loads(request.body)
            endpoint = data["endpoint"]
            keys = data["keys"]
            p256dh = keys["p256dh"]
            auth = keys["auth"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return HttpResponseBadRequest("Invalid subscription payload")

        save_push_subscription(portal_user.user, endpoint, p256dh, auth)
        return JsonResponse({"status": "ok"})


class PortalPushUnsubscribeView(View):
    """POST body: {"endpoint": ...} - removes a Web Push subscription for the
    logged-in portal user."""

    def post(self, request):
        import json

        from django.http import HttpResponseBadRequest

        from apps.core.push_service import delete_push_subscription

        portal_user = get_portal_user(request)
        if not portal_user:
            return HttpResponseForbidden("Not logged in")

        try:
            data = json.loads(request.body)
            endpoint = data["endpoint"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return HttpResponseBadRequest("Invalid payload")

        delete_push_subscription(portal_user.user, endpoint)
        return JsonResponse({"status": "ok"})
