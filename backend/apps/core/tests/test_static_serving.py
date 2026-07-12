"""
Regression guard: WhiteNoise must serve static files with DEBUG=False.

Without WhiteNoise (or with it misconfigured), Daphne/ASGI returns 404 for all
/static/* requests in production because Django only auto-serves static files
via runserver (DEBUG=True). This test catches that regression.
"""

import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings


class WhiteNoiseStaticServingTest(TestCase):
    """Static files must be served (200) in production mode via WhiteNoise middleware."""

    def test_favicon_returns_200_in_production_mode(self):
        tmp_root = tempfile.mkdtemp()
        try:
            # Populate a temp STATIC_ROOT using plain storage (no manifest needed here)
            with override_settings(
                STATIC_ROOT=tmp_root,
                STORAGES={
                    "default": {
                        "BACKEND": "django.core.files.storage.FileSystemStorage",
                    },
                    "staticfiles": {
                        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                    },
                },
            ):
                call_command("collectstatic", "--noinput", verbosity=0)

            # Overriding MIDDLEWARE forces re-initialisation of WhiteNoise with the
            # populated tmp_root. DEBUG=False simulates the production scenario that
            # previously returned 404 for all /static/* requests.
            with override_settings(
                DEBUG=False,
                STATIC_ROOT=tmp_root,
                MIDDLEWARE=[
                    "django.middleware.security.SecurityMiddleware",
                    "whitenoise.middleware.WhiteNoiseMiddleware",
                    "django.contrib.sessions.middleware.SessionMiddleware",
                    "django.middleware.common.CommonMiddleware",
                ],
            ):
                response = self.client.get("/static/icons/favicon.ico")
                self.assertEqual(
                    response.status_code,
                    200,
                    "WhiteNoise must serve /static/icons/favicon.ico in production mode "
                    "(DEBUG=False). Got 404 — check MIDDLEWARE and WhiteNoise configuration.",
                )
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)
