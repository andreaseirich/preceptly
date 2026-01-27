"""
Service for sending email notifications related to lessons.
"""

import logging
import sys
import threading
from datetime import timedelta

from apps.lessons.models import Lesson
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def send_booking_notification(lesson: Lesson) -> bool:
    """
    Send email notification when a lesson is booked through the booking page.

    Args:
        lesson: The Lesson instance that was booked

    Returns:
        True if email was sent successfully, False otherwise
    """
    logger.info(f"Attempting to send booking notification for lesson {lesson.id}")
    # Also print to stdout for better visibility in Railway logs
    print(
        f"[EMAIL_SERVICE] Attempting to send booking notification for lesson {lesson.id}",
        file=sys.stdout,
        flush=True,
    )

    # Get notification email address
    notification_email = getattr(settings, "NOTIFICATION_EMAIL", None)
    logger.debug(f"NOTIFICATION_EMAIL from settings: {notification_email}")
    print(
        f"[EMAIL_SERVICE] NOTIFICATION_EMAIL from settings: {notification_email}",
        file=sys.stdout,
        flush=True,
    )

    if not notification_email:
        # Fallback: try to get email from first user
        from django.contrib.auth.models import User

        try:
            first_user = User.objects.filter(is_superuser=True).first()
            if not first_user:
                first_user = User.objects.first()
            if first_user and first_user.email:
                notification_email = first_user.email
                logger.info(f"Using fallback email from user: {notification_email}")
        except Exception as e:
            logger.warning(f"Could not get user email: {e}", exc_info=True)

    if not notification_email:
        error_msg = "No notification email configured. Skipping email notification. Please set NOTIFICATION_EMAIL environment variable."
        logger.error(error_msg)
        print(f"[EMAIL_SERVICE] ERROR: {error_msg}", file=sys.stdout, flush=True)
        return False

    logger.info(f"Sending booking notification email to {notification_email}")
    print(
        f"[EMAIL_SERVICE] Sending booking notification email to {notification_email}",
        file=sys.stdout,
        flush=True,
    )

    # Calculate end time
    from datetime import datetime

    start_datetime = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time))
    end_datetime = start_datetime + timedelta(minutes=lesson.duration_minutes)
    end_time = end_datetime.time()

    # Prepare context for email template
    context = {
        "lesson": lesson,
        "end_time": end_time,
    }

    # Render email templates
    subject = _("New Lesson Booking: {student} - {date}").format(
        student=lesson.contract.student, date=lesson.date.strftime("%d.%m.%Y")
    )

    html_message = render_to_string("lessons/email_booking_notification.html", context)
    plain_message = render_to_string("lessons/email_booking_notification.txt", context)

    # Log email backend configuration
    email_backend = getattr(settings, "EMAIL_BACKEND", "not set")
    logger.info(f"Using email backend: {email_backend}")
    print(
        f"[EMAIL_SERVICE] Using email backend: {email_backend}",
        file=sys.stdout,
        flush=True,
    )

    if email_backend == "django.core.mail.backends.console.EmailBackend":
        warning_msg = (
            "EMAIL_BACKEND is set to console backend. "
            "Emails will only be printed to console, not actually sent. "
            "Set EMAIL_BACKEND to 'django.core.mail.backends.smtp.EmailBackend' to send real emails."
        )
        logger.warning(warning_msg)
        print(f"[EMAIL_SERVICE] WARNING: {warning_msg}", file=sys.stdout, flush=True)

    # Send email with timeout to prevent worker timeout
    email_timeout = 10  # 10 seconds timeout
    email_sent = [False]
    email_error = [None]

    def send_email_thread():
        """Send email in a separate thread with timeout protection."""
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification_email],
                html_message=html_message,
                fail_silently=False,
            )
            email_sent[0] = True
        except Exception as e:
            email_error[0] = e

    try:
        # Start email sending in a thread
        email_thread = threading.Thread(target=send_email_thread, daemon=True)
        email_thread.start()
        email_thread.join(timeout=email_timeout)

        if email_thread.is_alive():
            # Thread is still running, timeout occurred
            timeout_msg = (
                f"Email sending timed out after {email_timeout} seconds for lesson {lesson.id}"
            )
            logger.warning(timeout_msg)
            print(f"[EMAIL_SERVICE] WARNING: {timeout_msg}", file=sys.stdout, flush=True)
            return False

        if email_error[0]:
            # Email sending failed
            error_msg = f"Failed to send booking notification email to {notification_email} for lesson {lesson.id}: {email_error[0]}"
            logger.error(error_msg, exc_info=True)
            print(f"[EMAIL_SERVICE] ERROR: {error_msg}", file=sys.stdout, flush=True)
            return False

        if email_sent[0]:
            success_msg = f"Booking notification email sent successfully to {notification_email} for lesson {lesson.id}"
            logger.info(success_msg)
            print(f"[EMAIL_SERVICE] SUCCESS: {success_msg}", file=sys.stdout, flush=True)
            return True
        else:
            # Should not happen, but handle it
            error_msg = f"Email sending completed but status unknown for lesson {lesson.id}"
            logger.warning(error_msg)
            print(f"[EMAIL_SERVICE] WARNING: {error_msg}", file=sys.stdout, flush=True)
            return False

    except Exception as e:
        error_msg = f"Unexpected error while sending email for lesson {lesson.id}: {e}"
        logger.error(error_msg, exc_info=True)
        print(f"[EMAIL_SERVICE] ERROR: {error_msg}", file=sys.stdout, flush=True)
        return False
