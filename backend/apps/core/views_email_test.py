"""
Test endpoint for email functionality.
Only available in DEBUG mode or for superusers.
"""

import logging

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


def is_superuser_or_debug(user):
    """Check if user is superuser or DEBUG is enabled."""
    return user.is_superuser or settings.DEBUG


@require_http_methods(["GET", "POST"])
@user_passes_test(is_superuser_or_debug)
def test_email(request):
    """
    Test endpoint to send a test email and check email configuration.

    GET: Returns email configuration (without sensitive data)
    POST: Sends a test email
    """
    if request.method == "GET":
        # Return email configuration
        notification_email = getattr(settings, "NOTIFICATION_EMAIL", None)
        email_backend = getattr(settings, "EMAIL_BACKEND", "not set")
        email_host = getattr(settings, "EMAIL_HOST", "not set")
        email_port = getattr(settings, "EMAIL_PORT", "not set")
        default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "not set")

        return JsonResponse(
            {
                "email_backend": email_backend,
                "email_host": email_host,
                "email_port": email_port,
                "default_from_email": default_from,
                "notification_email": notification_email if notification_email else "not set",
                "email_use_tls": getattr(settings, "EMAIL_USE_TLS", False),
                "email_use_ssl": getattr(settings, "EMAIL_USE_SSL", False),
                "email_host_user": getattr(settings, "EMAIL_HOST_USER", "not set")[:3] + "***"
                if getattr(settings, "EMAIL_HOST_USER", None)
                else "not set",
            }
        )

    # POST: Send test email
    logger.info("Test email endpoint called")
    notification_email = getattr(settings, "NOTIFICATION_EMAIL", None)

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
        logger.error("No notification email configured")
        return JsonResponse(
            {
                "success": False,
                "error": "No notification email configured. Set NOTIFICATION_EMAIL environment variable.",
            },
            status=400,
        )

    email_backend = getattr(settings, "EMAIL_BACKEND", "not set")
    logger.info(f"Using email backend: {email_backend}")
    logger.info(f"Sending test email to: {notification_email}")

    try:
        send_mail(
            subject="TutorFlow Test Email",
            message="This is a test email from TutorFlow. If you receive this, email configuration is working correctly.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification_email],
            fail_silently=False,
        )
        logger.info(f"Test email sent successfully to {notification_email}")
        return JsonResponse(
            {
                "success": True,
                "message": f"Test email sent successfully to {notification_email}",
                "email_backend": email_backend,
            }
        )
    except Exception as e:
        # Log detailed error but don't expose it to the client
        logger.error(f"Failed to send test email: {e}", exc_info=True)
        # Return generic error message to avoid information exposure
        return JsonResponse(
            {
                "success": False,
                "error": "Failed to send test email. Check server logs for details.",
                "email_backend": email_backend,
            },
            status=500,
        )
