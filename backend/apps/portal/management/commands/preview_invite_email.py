"""Management command to send a preview of the portal invite email."""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string


class Command(BaseCommand):
    help = "Send a preview of the portal invite email to a given address."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default="contact@andicode.de",
            help="Recipient address (default: contact@andicode.de)",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        recipient = options["to"]
        site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")

        for role in ("student", "parent"):
            context = {
                "student": type("S", (), {"full_name": "Max Mustermann"})(),
                "activate_url": f"{site_url}/portal/activate/EXAMPLE-TOKEN-123/",
                "tutor_name": "Andreas Eirich",
                "role": role,
                "site_url": site_url,
            }
            html_message = render_to_string("portal/email/invite.html", context)
            plain_message = render_to_string("portal/email/invite.txt", context)
            subject = f"[VORSCHAU] Portal-Einladung ({role})"
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                html_message=html_message,
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Vorschau ({role}) gesendet an {recipient}"))
