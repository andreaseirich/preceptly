"""Datenbank-Einstellungen, die sich in Tests nicht von selbst zeigen: Die Tests
laufen mit SQLite, der Zweig für DATABASE_URL (Produktion) wird nie ausgeführt."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DatabaseConfigTest(SimpleTestCase):
    def test_no_persistent_connections_under_asgi(self):
        source = (Path(settings.BASE_DIR) / "tutorflow" / "settings.py").read_text(encoding="utf-8")
        self.assertIn("conn_max_age=0", source)
        self.assertNotRegex(source, r"conn_max_age=[1-9]")
