"""
Tests for booking notification email service.
"""

from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from apps.contracts.models import Contract
from apps.lessons.email_service import send_booking_notification
from apps.lessons.models import Lesson
from apps.students.models import Student
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings


class SendBookingNotificationTest(TestCase):
    """Tests for send_booking_notification."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")
        self.student = Student.objects.create(
            user=self.user, first_name="Test", last_name="Student"
        )
        self.contract = Contract.objects.create(
            student=self.student,
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=date(2024, 1, 1),
        )
        self.lesson = Lesson.objects.create(
            contract=self.contract,
            date=date(2024, 2, 15),
            start_time=time(10, 0),
            duration_minutes=60,
            status="planned",
        )

    @override_settings(DEBUG=False, NOTIFICATION_EMAIL="")
    @patch("apps.lessons.email_service.send_mail")
    def test_returns_false_no_fallback_when_debug_false_and_notification_email_missing(
        self, mock_send_mail
    ):
        """DEBUG=False and NOTIFICATION_EMAIL missing -> returns False, no user fallback."""
        result = send_booking_notification(self.lesson)
        self.assertFalse(result)
        mock_send_mail.assert_not_called()

    @override_settings(DEBUG=False, NOTIFICATION_EMAIL="")
    @patch("apps.lessons.email_service.send_mail")
    def test_no_user_queried_when_debug_false(self, mock_send_mail):
        """DEBUG=False and NOTIFICATION_EMAIL missing -> no User fallback attempted."""
        with patch.object(User, "objects") as mock_user_manager:
            result = send_booking_notification(self.lesson)
            self.assertFalse(result)
            mock_send_mail.assert_not_called()
            mock_user_manager.filter.assert_not_called()

    @override_settings(NOTIFICATION_EMAIL="tutor@example.com")
    @patch("apps.lessons.email_service.send_mail")
    def test_send_mail_called_with_correct_params_when_notification_email_set(self, mock_send_mail):
        """NOTIFICATION_EMAIL present -> send_mail called with correct subject/from/to."""
        mock_send_mail.return_value = 1
        result = send_booking_notification(self.lesson)
        self.assertTrue(result)
        mock_send_mail.assert_called_once()
        call_kw = mock_send_mail.call_args[1]
        self.assertEqual(call_kw["recipient_list"], ["tutor@example.com"])
        self.assertEqual(call_kw["from_email"], settings.DEFAULT_FROM_EMAIL)
        self.assertIn("New Lesson Booking", call_kw["subject"])
        self.assertIn("Test Student", call_kw["subject"])
        self.assertIn("15.02.2024", call_kw["subject"])

    @override_settings(NOTIFICATION_EMAIL="tutor@example.com")
    @patch("apps.lessons.email_service.send_mail")
    def test_smtp_exception_caught_returns_false(self, mock_send_mail):
        """SMTPException raised -> caught, returns False, no re-raise."""
        import smtplib

        mock_send_mail.side_effect = smtplib.SMTPException("Connection refused")
        result = send_booking_notification(self.lesson)
        self.assertFalse(result)

    @override_settings(NOTIFICATION_EMAIL="tutor@example.com")
    @patch("apps.lessons.email_service.send_mail")
    def test_generic_exception_caught_returns_false(self, mock_send_mail):
        """Generic Exception raised -> caught, returns False, no re-raise."""
        mock_send_mail.side_effect = RuntimeError("Network error")
        result = send_booking_notification(self.lesson)
        self.assertFalse(result)
