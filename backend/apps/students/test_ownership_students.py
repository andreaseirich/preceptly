"""
Ownership/tenant isolation tests for Students.
Tutor B must never see or modify Tutor A's students. Cross-user access => 404.
"""

from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class StudentOwnershipIsolationTest(TestCase):
    """Tutor B cannot see/update/delete Tutor A's students. 404 on cross-user access."""

    def setUp(self):
        self.client = Client()
        self.tutor_a = User.objects.create_user(username="tutor_a", password="test")
        self.tutor_b = User.objects.create_user(username="tutor_b", password="test")

        self.student_a = Student.objects.create(
            user=self.tutor_a,
            first_name="Alice",
            last_name="AStudent",
        )
        self.student_b = Student.objects.create(
            user=self.tutor_b,
            first_name="Bob",
            last_name="BStudent",
        )

    def test_tutor_a_list_shows_only_own_students(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("students:list"))
        self.assertEqual(response.status_code, 200)
        ids = [s.pk for s in response.context["students"]]
        self.assertIn(self.student_a.pk, ids)
        self.assertNotIn(self.student_b.pk, ids)

    def test_tutor_b_list_shows_only_own_students(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("students:list"))
        self.assertEqual(response.status_code, 200)
        ids = [s.pk for s in response.context["students"]]
        self.assertIn(self.student_b.pk, ids)
        self.assertNotIn(self.student_a.pk, ids)

    def test_tutor_a_can_view_own_student_detail(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("students:detail", kwargs={"pk": self.student_a.pk}))
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_student_detail(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("students:detail", kwargs={"pk": self.student_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_a_gets_404_for_tutor_b_student_detail(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("students:detail", kwargs={"pk": self.student_b.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_a_can_update_own_student(self):
        self.client.force_login(self.tutor_a)
        response = self.client.get(reverse("students:update", kwargs={"pk": self.student_a.pk}))
        self.assertEqual(response.status_code, 200)

    def test_tutor_b_gets_404_for_tutor_a_student_update(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("students:update", kwargs={"pk": self.student_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_gets_404_for_tutor_a_student_delete_get(self):
        self.client.force_login(self.tutor_b)
        response = self.client.get(reverse("students:delete", kwargs={"pk": self.student_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_tutor_b_cannot_delete_tutor_a_student_post(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("students:delete", kwargs={"pk": self.student_a.pk}),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Student.objects.filter(pk=self.student_a.pk).exists())

    def test_tutor_b_gets_404_for_regenerate_booking_code_on_tutor_a_student(self):
        self.client.force_login(self.tutor_b)
        response = self.client.post(
            reverse("students:regenerate_booking_code", kwargs={"pk": self.student_a.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
