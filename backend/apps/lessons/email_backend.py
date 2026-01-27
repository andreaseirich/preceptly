"""
Custom email backend with timeout support.
"""

import smtplib
import socket

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


class TimeoutSMTPEmailBackend(SMTPEmailBackend):
    """
    SMTP email backend with timeout support.

    This backend extends Django's SMTP backend to add socket timeouts,
    preventing email sending from hanging indefinitely.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the backend with timeout support.
        Timeout is read from settings.EMAIL_TIMEOUT (default: 10 seconds).
        """
        # Get timeout from settings or use default
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", 10)
        super().__init__(*args, **kwargs)

    def open(self):
        """
        Open a connection to the SMTP server with timeout.
        """
        if self.connection:
            return False

        try:
            # Set socket timeout before connecting
            socket.setdefaulttimeout(self.timeout)

            # Create SMTP connection
            connection_class = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
            self.connection = connection_class(self.host, self.port, timeout=self.timeout)

            # Enable TLS if needed
            if self.use_tls and not self.use_ssl:
                self.connection.starttls()

            # Authenticate if credentials are provided
            if self.username and self.password:
                self.connection.login(self.username, self.password)

            return True
        except (smtplib.SMTPException, socket.error, OSError):
            if not self.fail_silently:
                raise
            return False
        finally:
            # Reset socket timeout to default
            socket.setdefaulttimeout(None)
