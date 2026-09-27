"""Schrift auf Akzent- und Erfolgsflächen - vor allem im Dunkelmodus
(Prüfbericht 27.09.2026, B1: Weiß auf hellem Türkis hatte 1,9:1).

Schrift auf var(--accent)/var(--success) nimmt var(--on-accent)/var(--on-success).
Jede Vorlage, die die Farben selbst festlegt, legt auch diese Tokens fest - hell
Weiß, dunkel Dunkelgrau - und die Tests rechnen den Kontrast nach WCAG nach.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

APPS = Path(settings.BASE_DIR) / "apps"
BG = re.compile(r"background(?:-color)?\s*:\s*var\(--(?:accent|success)(?:-hover)?\)")
WHITE = re.compile(r"(?<![-\w])color\s*:\s*(?:white|#fff\b|#ffffff)", re.I)


def _luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    chans = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _templates():
    return (p for p in APPS.rglob("*.html") if "email" not in p.parts)


class AccentTextTokenTest(SimpleTestCase):
    def test_no_hard_white_on_accent_or_success(self):
        found = []
        for path in _templates():
            text = path.read_text(encoding="utf-8")
            segments = re.findall(r"\{[^{}]*\}", text) + re.findall(r'style="[^"]*"', text)
            for segment in segments:
                if BG.search(segment) and WHITE.search(segment):
                    found.append(f"{path.relative_to(APPS)}: {segment[:80]}")
        self.assertEqual(found, [], "Schrift auf Akzentflächen: var(--on-accent, #fff)")

    def test_every_colour_definition_brings_readable_text(self):
        """Zu jedem --accent/--success gehört ein --on-… mit mindestens 4,5:1."""
        checked = 0
        for path in _templates():
            lines = path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                m = re.match(r"\s*--(accent|success):\s*(#[0-9a-fA-F]{3,6})\s*;", line)
                if not m:
                    continue
                kind, surface = m.groups()
                nxt = re.match(rf"\s*--on-{kind}:\s*(#[0-9a-fA-F]{{3,6}})", lines[i + 1])
                with self.subTest(datei=path.name, farbe=surface):
                    self.assertIsNotNone(nxt, f"--on-{kind} fehlt nach --{kind}")
                    self.assertGreaterEqual(_contrast(surface, nxt.group(1)), 4.5)
                checked += 1
        self.assertGreaterEqual(checked, 12)

    def test_rating_stars_are_readable_in_both_themes(self):
        text = (APPS / "core/templates/core/base.html").read_text(encoding="utf-8")
        markers = re.findall(r"--marker:\s*(#[0-9a-fA-F]{6})", text)
        backgrounds = re.findall(r"--bg-secondary:\s*(#[0-9a-fA-F]{6})", text)
        self.assertEqual(len(markers), len(backgrounds))
        for marker, background in zip(markers, backgrounds, strict=True):
            with self.subTest(stern=marker, grund=background):
                self.assertGreaterEqual(_contrast(marker, background), 4.5)


class LoginAutocompleteTest(TestCase):
    """WCAG 1.3.5: Passwort-Manager und Handys füllen zuverlässig aus."""

    def test_tutor_login_fields_name_their_purpose(self):
        response = self.client.get(reverse("core:login"))

        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
