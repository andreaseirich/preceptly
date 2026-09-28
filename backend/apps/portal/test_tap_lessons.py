"""Termine im Portal direkt antippen - Anlass: Eine Mutter fand am 27.09.2026
„Verschieben“ auf dem Handy nicht, weil die Knöpfe rechts außerhalb lagen."""

from datetime import date, time, timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.lessons.models import Lesson
from apps.portal.tests_portal import (
    _make_contract,
    _make_portal_user,
    _make_student_link,
    _make_tutor,
)


class TapLessonTest(TestCase):
    def setUp(self):
        self.tutor = _make_tutor("tutor_tap")
        self.contract = _make_contract(self.tutor)
        self.student = _make_portal_user(self.tutor, "student", "schueler_tap", "pw_portal")
        _make_student_link(self.student, self.contract, active=True)
        self.lesson = self._lesson(2)
        session = self.client.session
        session["portal_user_id"] = self.student.pk
        session.save()

    def _lesson(self, days_ahead, status="planned"):
        return Lesson.objects.create(
            contract=self.contract,
            date=date.today() + timedelta(days=days_ahead),
            start_time=time(15, 30),
            duration_minutes=60,
            status=status,
        )

    def _detail(self, lesson):
        return reverse("portal:student_lesson_detail", args=[lesson.pk])

    def test_whole_row_opens_the_lesson(self):
        for page in ("portal:student_lessons", "portal:student_home"):
            with self.subTest(seite=page):
                response = self.client.get(reverse(page))
                self.assertContains(response, f'data-href="{self._detail(self.lesson)}"')
                # auch ohne JavaScript und per Tastatur erreichbar
                self.assertContains(
                    response, f'class="lesson-link" href="{self._detail(self.lesson)}"'
                )

    def test_buttons_in_the_row_keep_their_own_action(self):
        response = self.client.get(reverse("portal:student_lessons"))

        self.assertContains(response, "<td data-stop-propagation", count=2)

    def test_dashboard_offers_rescheduling_directly(self):
        response = self.client.get(reverse("portal:student_home"))

        self.assertContains(response, reverse("portal:session_reschedule", args=[self.lesson.pk]))

    def test_detail_page_offers_reschedule_and_cancel_for_planned_lessons(self):
        response = self.client.get(self._detail(self.lesson))

        self.assertContains(response, reverse("portal:session_reschedule", args=[self.lesson.pk]))
        self.assertContains(response, reverse("portal:session_cancel", args=[self.lesson.pk]))

    def test_detail_page_offers_no_changes_for_past_lessons(self):
        taught = self._lesson(-7, status="taught")

        response = self.client.get(self._detail(taught))

        self.assertNotContains(response, reverse("portal:session_reschedule", args=[taught.pk]))
        self.assertNotContains(response, "Termin ändern")

    def test_dashboard_loads_meeting_rooms_in_one_go(self):
        url = reverse("portal:student_home")
        self.client.get(url)
        with CaptureQueriesContext(connection) as few:
            self.client.get(url)
        for day in range(3, 7):
            self._lesson(day)
        with CaptureQueriesContext(connection) as many:
            self.client.get(url)

        self.assertLessEqual(len(many.captured_queries), len(few.captured_queries))
