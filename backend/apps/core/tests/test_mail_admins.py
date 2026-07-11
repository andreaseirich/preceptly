import logging

from django.core import mail
from django.test import SimpleTestCase, override_settings

_ADMIN_EMAIL = "admin@example.com"


@override_settings(
    ADMINS=[(_ADMIN_EMAIL, _ADMIN_EMAIL)],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class MailAdminsRecipientTest(SimpleTestCase):
    def test_admin_mail_sent_to_full_email_address(self):
        mail.outbox.clear()
        logger = logging.getLogger("django")
        try:
            raise RuntimeError("deliberate test error")
        except RuntimeError:
            logger.error("Deliberate test error triggering admin mail", exc_info=True)

        self.assertEqual(len(mail.outbox), 1, "Expected exactly one admin email")
        recipients = mail.outbox[0].to
        self.assertEqual(recipients, [_ADMIN_EMAIL])
