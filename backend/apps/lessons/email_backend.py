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
        Verwendet explizites timeout= im SMTP-Konstruktor statt socket.setdefaulttimeout(),
        um prozessglobale Side-Effects auf andere Threads zu vermeiden.
        """
        if self.connection:
            return False

        try:
            connection_class = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
            self.connection = connection_class(self.host, self.port, timeout=self.timeout)

            if self.use_tls and not self.use_ssl:
                self.connection.starttls()

            if self.username and self.password:
                self.connection.login(self.username, self.password)

            return True
        except socket.timeout as err:
            if not self.fail_silently:
                raise smtplib.SMTPConnectError(
                    421, f"SMTP connection timed out after {self.timeout}s"
                ) from err
            return False
        except (smtplib.SMTPException, socket.error, OSError):
            if not self.fail_silently:
                raise
            return False
