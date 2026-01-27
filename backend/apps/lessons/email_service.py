"""
Service for sending email notifications related to lessons.
"""

import logging
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
    
    # Get notification email address
    notification_email = getattr(settings, "NOTIFICATION_EMAIL", None)
    logger.debug(f"NOTIFICATION_EMAIL from settings: {notification_email}")
    
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
        logger.error("No notification email configured. Skipping email notification. Please set NOTIFICATION_EMAIL environment variable.")
        return False
    
    logger.info(f"Sending booking notification email to {notification_email}")

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
    
    if email_backend == "django.core.mail.backends.console.EmailBackend":
        logger.warning(
            "EMAIL_BACKEND is set to console backend. "
            "Emails will only be printed to console, not actually sent. "
            "Set EMAIL_BACKEND to 'django.core.mail.backends.smtp.EmailBackend' to send real emails."
        )
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(
            f"Booking notification email sent successfully to {notification_email} for lesson {lesson.id}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to send booking notification email to {notification_email} for lesson {lesson.id}: {e}",
            exc_info=True
        )
        return False
