"""
Service for sending email notifications related to lessons.
"""

import logging
from datetime import datetime, timedelta

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
    notification_email = (getattr(settings, "NOTIFICATION_EMAIL", None) or "").strip()

    if not notification_email:
        if settings.DEBUG:
            # Fallback in DEBUG: try first superuser/first user
            try:
                from django.contrib.auth.models import User

                first_user = User.objects.filter(is_superuser=True).first()
                if not first_user:
                    first_user = User.objects.first()
                if first_user and (first_user.email or "").strip():
                    notification_email = (first_user.email or "").strip()
                    logger.debug("Using fallback notification email (DEBUG only)")
            except Exception as e:
                logger.warning("Fallback notification email lookup failed: %s", str(e)[:80])
        else:
            logger.warning("NOTIFICATION_EMAIL not set; skipping booking notification")
            return False

    if not notification_email:
        logger.warning("No notification email configured; skipping booking notification")
        return False

    start_datetime = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time))
    end_datetime = start_datetime + timedelta(minutes=lesson.duration_minutes)
    end_time = end_datetime.time()

    context = {"lesson": lesson, "end_time": end_time}
    subject = _("New Lesson Booking: {student} - {date}").format(
        student=lesson.contract.student, date=lesson.date.strftime("%d.%m.%Y")
    )
    html_message = render_to_string("lessons/email_booking_notification.html", context)
    plain_message = render_to_string("lessons/email_booking_notification.txt", context)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Booking notification sent for lesson %s", lesson.id)
        return True
    except Exception as e:
        logger.warning(
            "Booking notification send failed for lesson %s: %s",
            lesson.id,
            str(e)[:100],
            exc_info=False,
        )
        return False
