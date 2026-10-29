"""Annahmen hinter den Ignores im Sicherheits-Audit (siehe SECURITY.md, "Twisted 26.4.0 via Daphne").

Das CI-Audit ignoriert die Twisted-Lücke GHSA-vpp8-g58w-m8mp (HTTP/2 Rapid Reset), weil Preceptly Twisters HTTP/2-Server nicht
erreichbar betreibt. Diese Tests binden das Ignorieren an seine Voraussetzung: Schlagen sie fehl, ist die Lücke vermutlich doch
erreichbar, und die Entscheidung in SECURITY.md muss neu getroffen werden (nicht den Test löschen).
"""

import importlib.util
import pathlib
import re

from django.test import SimpleTestCase

REPO = pathlib.Path(__file__).resolve().parents[4]


class TwistedHttp2NotReachableTest(SimpleTestCase):
    def test_the_h2_package_is_not_installed(self):
        # Twisters HTTP/2-Server importiert h2 am Dateianfang und lässt sich ohne nicht laden.
        for name in ("h2", "hpack", "hyperframe"):
            with self.subTest(paket=name):
                self.assertIsNone(
                    importlib.util.find_spec(name),
                    f"{name} ist installiert: HTTP/2 in Twisted/Daphne wäre möglich, siehe SECURITY.md (GHSA-vpp8-g58w-m8mp)",
                )

    def test_requirements_do_not_ask_for_the_http2_extra(self):
        for name in ("requirements.txt", "requirements-dev.txt"):
            with self.subTest(datei=name):
                text = (REPO / name).read_text(encoding="utf-8").lower()
                self.assertNotRegex(text, r"twisted\[[^\]]*http2")
                self.assertNotRegex(text, r"(^|\n)\s*h2\s*[=<>~!]")

    def test_the_server_starts_without_a_tls_endpoint(self):
        # HTTP/2 braucht TLS (ALPN). Bei Preceptly endet TLS am Proxy von Railway, Daphne spricht nur einfaches HTTP.
        script = (REPO / "scripts" / "entrypoint.sh").read_text(encoding="utf-8")
        start = next(line for line in script.splitlines() if re.match(r"\s*exec\s+daphne\b", line))
        self.assertNotRegex(start, r"(-e|--endpoint)\b")
        self.assertNotRegex(start, r"ssl:|tls:|--ssl|--certfile|--keyfile")
