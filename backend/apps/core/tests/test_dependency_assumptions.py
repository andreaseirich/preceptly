"""Annahmen rund um die Abhängigkeiten (siehe SECURITY.md, "Twisted (via Daphne)").

Bis zum 17.11.2026 ignorierte das CI-Audit die Twisted-Lücke GHSA-vpp8-g58w-m8mp (HTTP/2 Rapid Reset), weil Preceptly Twisters
HTTP/2-Server nicht erreichbar betreibt. Mit Twisted 26.10.0 ist die Meldung behoben und das Ignore entfernt. Die Tests zu HTTP/2
bleiben als Absicherung: Preceptly braucht kein HTTP/2, und ohne den Server bleibt die Angriffsfläche kleiner. Schlagen sie fehl,
ist HTTP/2 vermutlich ungewollt eingeschaltet worden (nicht den Test löschen, die Entscheidung in SECURITY.md neu treffen).

Dazu kommt die Hygiene des Audits: Jedes Ignore im CI muss in SECURITY.md begründet sein, und Pygments und Twisted kommen aus
Veröffentlichungen der behobenen Version, nicht aus einem Git-Stand.
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


class AuditHygieneTest(SimpleTestCase):
    def requirements(self):
        return (REPO / "requirements.txt").read_text(encoding="utf-8")

    def test_every_ignore_in_ci_is_documented_in_security_md(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        security = (REPO / "SECURITY.md").read_text(encoding="utf-8")
        code = "\n".join(
            line for line in ci.splitlines() if not line.lstrip().startswith("#")
        )  # Kommentare zählen nicht
        for vuln in re.findall(r"--ignore-vuln\s+(\S+)", code):
            with self.subTest(meldung=vuln):
                self.assertIn(
                    vuln,
                    security,
                    f"{vuln} wird in ci.yml ignoriert, steht aber nicht in SECURITY.md",
                )

    def test_pygments_comes_from_a_release_not_from_git(self):
        text = self.requirements()

        self.assertRegex(text, r"(?m)^Pygments==\d")
        self.assertNotRegex(text, r"(?m)^[^#\n]*git\+")

    def test_twisted_has_a_floor_at_the_release_that_fixed_the_advisories(self):
        match = re.search(r"(?mi)^twisted(?:\[[^\]]*\])?>=([\d.]+)", self.requirements())

        self.assertIsNotNone(match, "Twisted>=26.10.0 fehlt in requirements.txt")
        self.assertGreaterEqual(tuple(int(part) for part in match.group(1).split(".")), (26, 10, 0))
