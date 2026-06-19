"""
Service for sending email notifications related to lessons.
"""

import logging
import re
from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.lessons.models import Lesson

logger = logging.getLogger(__name__)


def _sanitize_header(value: str) -> str:
    """Entfernt alle Control-Zeichen und Unicode-Zeilentrenner aus E-Mail-Header-Werten."""
    value = re.sub(r"[\r\n\x00-\x1f\x7f\u2028\u2029]", " ", value or "")
    return value.strip()[:200]


def send_booking_notification(lesson: Lesson) -> bool:
    """
    Send email notification when a lesson is booked through the booking page.

    Args:
        lesson: The Lesson instance that was booked

    Returns:
        True if email was sent successfully, False otherwise
    """
    from django.core.cache import cache

    notification_email = (getattr(settings, "NOTIFICATION_EMAIL", None) or "").strip()

    if not notification_email:
        logger.warning("NOTIFICATION_EMAIL not set; skipping booking notification")
        return False

    # [LOW FIX] Rate-Limiting: max. 20 Notifications pro Stunde pro Tenant
    rate_limit_key = f"booking_notify:{lesson.contract.user_id}"
    current_count = cache.get(rate_limit_key, 0)
    if current_count > 20:
        logger.warning(
            "Notification rate limit hit for user %s; skipping booking notification for lesson %s",
            lesson.contract.user_id,
            lesson.id,
        )
        return False
    # Zähler erhöhen (atomic-safe durch kurze TTL-Fenster)
    cache.set(rate_limit_key, current_count + 1, 3600)

    start_datetime = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time))
    end_datetime = start_datetime + timedelta(minutes=lesson.duration_minutes)
    end_time = end_datetime.time()

    context = {"lesson": lesson, "end_time": end_time}

    # [MEDIUM FIX] Subject vollständig über _sanitize_header führen (inkl. Unicode-Zeilentrenner)
    subject = _sanitize_header(
        str(
            _("New Lesson Booking: {student} - {date}").format(
                student=_sanitize_header(lesson.contract.full_name),
                date=lesson.date.strftime("%d.%m.%Y"),
            )
        )
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
    except Exception:
        logger.exception(
            "Booking notification send failed for lesson %s",
            lesson.id,
        )
        return False
