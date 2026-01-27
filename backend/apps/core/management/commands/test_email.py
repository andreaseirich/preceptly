"""
Django management command to test email functionality.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test email configuration by sending a test email"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Email address to send test email to (overrides NOTIFICATION_EMAIL)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Testing email configuration...")
        
        # Get notification email
        notification_email = options.get("email") or getattr(settings, "NOTIFICATION_EMAIL", None)
        
        if not notification_email:
            # Fallback: try to get email from first user
            from django.contrib.auth.models import User
            
            try:
                first_user = User.objects.filter(is_superuser=True).first()
                if not first_user:
                    first_user = User.objects.first()
                if first_user and first_user.email:
                    notification_email = first_user.email
                    self.stdout.write(f"Using fallback email from user: {notification_email}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not get user email: {e}"))
        
        if not notification_email:
            self.stdout.write(
                self.style.ERROR(
                    "No notification email configured. "
                    "Set NOTIFICATION_EMAIL environment variable or use --email option."
                )
            )
            return
        
        # Display email configuration
        email_backend = getattr(settings, "EMAIL_BACKEND", "not set")
        self.stdout.write(f"Email backend: {email_backend}")
        self.stdout.write(f"Email host: {getattr(settings, 'EMAIL_HOST', 'not set')}")
        self.stdout.write(f"Email port: {getattr(settings, 'EMAIL_PORT', 'not set')}")
        self.stdout.write(f"From email: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'not set')}")
        self.stdout.write(f"To email: {notification_email}")
        
        if email_backend == "django.core.mail.backends.console.EmailBackend":
            self.stdout.write(
                self.style.WARNING(
                    "EMAIL_BACKEND is set to console backend. "
                    "Emails will only be printed to console, not actually sent."
                )
            )
        
        # Send test email
        self.stdout.write("\nSending test email...")
        logger.info(f"Attempting to send test email to {notification_email}")
        
        try:
            send_mail(
                subject="TutorFlow Test Email",
                message="This is a test email from TutorFlow. If you receive this, email configuration is working correctly.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification_email],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Test email sent successfully to {notification_email}"))
            logger.info(f"Test email sent successfully to {notification_email}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to send test email: {e}"))
            logger.error(f"Failed to send test email: {e}", exc_info=True)
