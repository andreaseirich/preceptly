"""Management command: register this app as an e-recht24 client and pull texts."""

from django.core.management.base import BaseCommand

from apps.core.erecht24_service import (
    delete_client,
    pull_imprint,
    pull_privacy_policy,
    register_client,
)


class Command(BaseCommand):
    help = "Register Preceptly as e-recht24 client and pull current legal texts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--push-uri",
            required=True,
            help="Public URL of the push webhook, e.g. https://preceptly.de/erecht24/push/",
        )
        parser.add_argument(
            "--delete",
            type=int,
            metavar="CLIENT_ID",
            help="Delete an existing client by ID before re-registering",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            result = delete_client(options["delete"])
            self.stdout.write("Deleted client " + str(options["delete"]) + ": " + str(result))

        self.stdout.write("Registering client …")
        result = register_client(options["push_uri"])

        if not result:
            self.stderr.write(self.style.ERROR("Registration failed — check API keys."))
            return

        client_id = result.get("client_id")
        secret = result.get("secret")

        self.stdout.write(self.style.SUCCESS(f"Client registered: id={client_id}"))
        self.stdout.write("")
        self.stdout.write("Add these to Railway environment variables:")
        self.stdout.write(f"  ERECHT24_CLIENT_ID={client_id}")
        self.stdout.write(f"  ERECHT24_PUSH_SECRET={secret}")
        self.stdout.write("")

        self.stdout.write("Pulling imprint …")
        pull_imprint()
        self.stdout.write("Pulling privacy policy …")
        pull_privacy_policy()
        self.stdout.write(self.style.SUCCESS("Done — legal texts are now cached."))
