"""Elternportal: Alle Stunden eines Kindes sind erreichbar.

`ParentStudentDetailView` zeigte früher nur die ersten 20 Stunden (`[:20]`) und 10 Notizen (`[:10]`), ohne Hinweis und ohne
Weg zu den übrigen. Jetzt gibt es Seiten (20 je Seite) und alle Notizen.
"""

from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.portal.models import ProgressNote
from apps.portal.tests_portal import _make_contract, _make_portal_user, _make_student_link


class ParentDetailPagesTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("portal_tutor", password="pw", email="pt@example.com")
        UserProfile.objects.create(user=self.tutor, subscription_tier="pro")
        self.contract = _make_contract(self.tutor)
        self.parent = _make_portal_user(self.tutor, "parent", "eltern1", "Portal-Passwort-1")
        _make_student_link(self.parent, self.contract, active=True)
        session = self.client.session
        session["portal_user_id"] = self.parent.pk
        session.save()
        for n in range(45):
            Lesson.objects.create(
                contract=self.contract,
                date=date(2026, 1, 1) + timedelta(days=n),
                start_time=time(10, 0),
                duration_minutes=60,
                status="taught",
            )

    def get(self, **params):
        return self.client.get(
            reverse("portal:parent_student_detail", args=[self.contract.pk]), params
        )

    def test_every_lesson_is_reachable_through_the_pages(self):
        shown = []
        for number in (1, 2, 3):
            response = self.get(page=number)
            self.assertEqual(response.status_code, 200)
            shown += [lesson.pk for lesson in response.context["lessons"]]

        self.assertEqual(len(shown), 45)
        self.assertEqual(len(set(shown)), 45, "eine Stunde steht auf zwei Seiten")
        self.assertEqual(set(shown), set(Lesson.objects.values_list("pk", flat=True)))

    def test_the_newest_lessons_come_first_and_the_page_links_exist(self):
        html = self.get().content.decode()

        first = list(self.get().context["lessons"])
        self.assertEqual(first[0].date, date(2026, 1, 1) + timedelta(days=44))
        self.assertIn('rel="next"', html)
        self.assertIn("?page=2", html)

    def test_a_wrong_page_number_gives_the_first_or_last_page_never_an_error(self):
        self.assertEqual(self.get(page="abc").context["page_obj"].number, 1)
        self.assertEqual(self.get(page="999").context["page_obj"].number, 3)

    def test_every_progress_note_is_shown(self):
        for n in range(14):
            ProgressNote.objects.create(contract=self.contract, tutor=self.tutor, text=f"Notiz {n}")

        self.assertEqual(len(self.get().context["progress_notes"]), 14, "früher nur die letzten 10")

    def test_a_parent_still_sees_only_the_children_linked_to_the_account(self):
        other = _make_contract(self.tutor)

        response = self.client.get(reverse("portal:parent_student_detail", args=[other.pk]))

        self.assertEqual(response.status_code, 404)
