from django.contrib.auth.models import User
from django.test import TestCase

from apps.students.models import Student


class StudentModelTest(TestCase):
    """Tests für das Student-Model."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_create_student(self):
        """Test: Student kann erstellt werden."""
        student = Student.objects.create(
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
            email="max@example.com",
            school="Gymnasium XY",
            grade="10. Klasse",
            subjects="Mathe, Deutsch",
        )
        self.assertEqual(student.full_name, "Max Mustermann")
        self.assertEqual(str(student), "Max Mustermann")
