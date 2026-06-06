import uuid

from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.portal.models import ParentStudentLink, PortalMessage, PortalUser, StudentPortalLink


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
            return redirect("portal:home")
        return render(request, self.template_name)

    def post(self, request):
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        error = None
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                portal_user = PortalUser.objects.get(user=user)
                request.session["portal_user_id"] = portal_user.pk
                return redirect("portal:home")
            else:
                error = _("Invalid password.")
        except (User.DoesNotExist, PortalUser.DoesNotExist):
            error = _("Account not found.")
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
        if link.student.user != portal_user.tutor:
            return HttpResponseForbidden()
        student = link.student
        import datetime

        from apps.lessons.models import Lesson

        today = datetime.date.today()
        upcoming = Lesson.objects.filter(
            contract__student=student,
            date__gte=today,
            status__in=["planned"],
        ).order_by("date", "start_time")[:5]
        recent = Lesson.objects.filter(
            contract__student=student,
            date__lt=today,
        ).order_by("-date", "-start_time")[:5]
        messages = PortalMessage.objects.filter(student=student).order_by("created_at")
        PortalMessage.objects.filter(student=student, read_by_portal=False).update(
            read_by_portal=True
        )
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "upcoming": upcoming,
                "recent": recent,
                "messages": messages,
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
        if link.student.user != portal_user.tutor:
            return HttpResponseForbidden()
        from apps.lessons.models import Lesson

        lessons = Lesson.objects.filter(
            contract__student=link.student,
        ).order_by("-date", "-start_time")
        return render(
            request,
            self.template_name,
            {
                "student": link.student,
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
        links = ParentStudentLink.objects.filter(parent=portal_user).select_related("student")
        students_data = []
        import datetime

        from apps.lessons.models import Lesson

        today = datetime.date.today()
        for link in links:
            upcoming = (
                Lesson.objects.filter(
                    contract__student=link.student,
                    date__gte=today,
                    status__in=["planned"],
                )
                .order_by("date", "start_time")
                .first()
            )
            unread = PortalMessage.objects.filter(
                student=link.student, read_by_portal=False
            ).count()
            students_data.append(
                {
                    "student": link.student,
                    "next_lesson": upcoming,
                    "unread_messages": unread,
                }
            )
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
        link = get_object_or_404(ParentStudentLink, parent=portal_user, student_id=student_pk)
        student = link.student
        from apps.lessons.models import Lesson

        lessons = Lesson.objects.filter(
            contract__student=student,
        ).order_by("-date", "-start_time")[:20]
        progress_notes = student.progress_notes.all()[:10]
        messages = PortalMessage.objects.filter(student=student).order_by("created_at")
        PortalMessage.objects.filter(student=student, read_by_portal=False).update(
            read_by_portal=True
        )
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "lessons": lessons,
                "progress_notes": progress_notes,
                "messages": messages,
                "portal_user": portal_user,
            },
        )


class PortalMessageView(View):
    template_name = "portal/messages.html"

    def _get_student_for_portal_user(self, portal_user, student_pk):
        if portal_user.role == "student":
            link = StudentPortalLink.objects.filter(
                portal_user=portal_user, is_active=True, student_id=student_pk
            ).first()
            if link and link.student.user != portal_user.tutor:
                return None
            return link.student if link else None
        else:
            link = ParentStudentLink.objects.filter(
                parent=portal_user, student_id=student_pk
            ).first()
            if link and link.student.user != portal_user.tutor:
                return None
            return link.student if link else None

    def get(self, request, student_pk):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        student = self._get_student_for_portal_user(portal_user, student_pk)
        if not student:
            return HttpResponseForbidden()
        messages = PortalMessage.objects.filter(student=student).order_by("created_at")
        PortalMessage.objects.filter(student=student, read_by_portal=False).update(
            read_by_portal=True
        )
        return render(
            request,
            self.template_name,
            {
                "student": student,
                "messages": messages,
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
                student=student,
                text=text,
            )
        return redirect("portal:messages", student_pk=student_pk)


class PortalActivateView(View):
    """Token-based activation: user sets own password, link becomes active.

    Works for both StudentPortalLink (student) and ParentStudentLink (parent).
    """

    template_name = "portal/activate.html"

    def _get_link(self, token):
        """Return (link, portal_user) for the given token, from either link model."""
        link = StudentPortalLink.objects.filter(invite_token=token).first()
        if link:
            return link, link.portal_user
        link = ParentStudentLink.objects.filter(invite_token=token).first()
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
        return render(request, self.template_name, {"token": token, "student": link.student})

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
                    "student": link.student,
                    "error": "Das Passwort muss mindestens 8 Zeichen lang sein.",
                },
            )
        if password != password2:
            return render(
                request,
                self.template_name,
                {
                    "token": token,
                    "student": link.student,
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

    def post(self, request):
        username = request.POST.get("username", "").strip()
        try:
            user = User.objects.get(username=username)
            portal_user = PortalUser.objects.get(user=user)
            # Reuse invite_token mechanism for reset
            if portal_user.role == "student":
                link = StudentPortalLink.objects.get(portal_user=portal_user)
            else:
                # Parent: use any of their StudentPortalLinks
                link = StudentPortalLink.objects.filter(portal_user=portal_user).first()
            if link:
                link.invite_token = uuid.uuid4().hex
                link.save()
                # Get recipient email: user.email if available, else student.email
                recipient = user.email or link.student.email
                if recipient:
                    from django.conf import settings
                    from django.core.mail import send_mail
                    from django.template.loader import render_to_string

                    site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
                    reset_url = f"{site_url}/portal/activate/{link.invite_token}/"
                    context = {
                        "student": link.student,
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
        except (User.DoesNotExist, PortalUser.DoesNotExist, StudentPortalLink.DoesNotExist):
            pass  # Don't reveal if user exists
        return render(request, self.template_name, {"sent": True})


class StudentLessonDetailView(View):
    template_name = "portal/student_lesson_detail.html"

    def get(self, request, pk):
        portal_user = get_portal_user(request)
        if not portal_user or portal_user.role != "student":
            return redirect("portal:login")
        link = get_object_or_404(StudentPortalLink, portal_user=portal_user, is_active=True)
        if link.student.user != portal_user.tutor:
            return HttpResponseForbidden()
        from apps.lessons.models import Lesson

        lesson = get_object_or_404(Lesson, pk=pk, contract__student=link.student)
        return render(
            request,
            self.template_name,
            {
                "lesson": lesson,
                "student": link.student,
                "portal_user": portal_user,
            },
        )
