from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract


class StudentModelTest(TestCase):
    """Tests für das Student-Model."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_create_student(self):
        """Test: Student kann erstellt werden."""
        student = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Max",
            last_name="Mustermann",
            email="max@example.com",
            school="Gymnasium XY",
            grade="10. Klasse",
            subjects="Mathe, Deutsch",
        )
        self.assertEqual(student.full_name, "Max Mustermann")
        self.assertIn("Max Mustermann", str(student))


class TutorDocumentUploadMagicByteTest(TestCase):
    """L3: tutor document upload path must validate magic bytes, not only extension."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tutor_magic", password="testpass123", email="tutor_magic@example.com"
        )
        self.client = Client()
        self.client.login(username="tutor_magic", password="testpass123")
        self.contract = Contract.objects.create(
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
            user=self.user,
            first_name="Magic",
            last_name="Student",
        )

    def test_fake_pdf_rejected_via_tutor_upload(self):
        """Tutor upload with mismatched magic bytes must be rejected."""
        fake_pdf = SimpleUploadedFile("evil.pdf", b"NOTAPDFCONTENT", content_type="application/pdf")
        url = reverse("students:documents", kwargs={"pk": self.contract.pk})
        resp = self.client.post(url, {"file": fake_pdf})
        self.assertEqual(resp.status_code, 302)
        from django.contrib.messages import get_messages

        msgs = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Inhalt" in m or "erlaubt" in m for m in msgs))

    def test_valid_pdf_accepted_via_tutor_upload(self):
        """Tutor upload with valid PDF magic bytes must be accepted."""
        valid_pdf = SimpleUploadedFile(
            "real.pdf", b"%PDF-1.4 dummy content", content_type="application/pdf"
        )
        url = reverse("students:documents", kwargs={"pk": self.contract.pk})
        resp = self.client.post(url, {"file": valid_pdf})
        self.assertEqual(resp.status_code, 302)
        from django.contrib.messages import get_messages

        msgs = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertFalse(any("Inhalt" in m for m in msgs))
