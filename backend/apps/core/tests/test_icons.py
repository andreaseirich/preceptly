"""Die Icons ({% icon %}) sind Dekor aus einem gemeinsamen Sprite und dürfen nur dort stehen, wo ein SVG hingehört.

Hintergrund: Beim Ablösen der Emojis aus den Vorlagen (20.11.2026) landete in zwei Kalender-Tooltips ein {% icon %} mitten in einem
title-Attribut. Ein Tooltip kann kein Bild zeigen; das Ergebnis wäre kaputtes HTML gewesen. Dieser Test schlägt an, sobald das wieder passiert,
sobald ein Icon-Name nicht im Sprite steht oder eine Vorlage {% icon %} nutzt, ohne {% load icons %}.
"""

import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase

from apps.core.icon_paths import ICON_PATHS

BACKEND = Path(settings.BASE_DIR)
ICON_TAG = re.compile(r"\{%\s*icon\s+\"([^\"]+)\"")


def _templates():
    for root in (BACKEND / "apps", BACKEND / "templates"):
        yield from root.rglob("*.html")


def _render(source):
    return Template("{% load icons %}" + source).render(Context({}))


class IconTagTest(SimpleTestCase):
    def test_an_icon_points_into_the_sprite_and_is_hidden_from_screen_readers(self):
        html = _render('{% icon "users" %}')

        self.assertIn('<use href="#i-users">', html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('focusable="false"', html)

    def test_an_extra_class_is_added(self):
        self.assertIn('class="icon nav-icon"', _render('{% icon "users" "nav-icon" %}'))

    def test_an_unknown_name_renders_nothing(self):
        self.assertEqual(_render('{% icon "gibt-es-nicht" %}').strip(), "")

    def test_the_sprite_has_one_symbol_per_icon(self):
        sprite = _render("{% icon_sprite %}")

        for name in ICON_PATHS:
            with self.subTest(icon=name):
                self.assertIn(f'<symbol id="i-{name}" viewBox="0 0 24 24">', sprite)

    def test_every_drawing_has_content(self):
        for name, paths in ICON_PATHS.items():
            with self.subTest(icon=name):
                self.assertRegex(paths, r"<(path|circle|rect|line|polyline|polygon|ellipse)\b")


class IconUsageTest(SimpleTestCase):
    def test_every_icon_name_used_in_a_template_exists(self):
        unknown = []
        for path in _templates():
            for name in ICON_TAG.findall(path.read_text(encoding="utf-8")):
                if name not in ICON_PATHS:
                    unknown.append(f"{path.relative_to(BACKEND)}: {name}")
        self.assertEqual(unknown, [])

    def test_no_icon_inside_an_html_attribute(self):
        """In title="…", alt="…", aria-label="…" usw. darf kein {% icon %} stehen: Dort gehört nur Text hin."""
        found = []
        for path in _templates():
            text = path.read_text(encoding="utf-8")
            for m in re.finditer(r"\b[\w:-]+=\"([^\"]*\{%\s*icon\b[^\"]*)\"", text):
                line = text.count("\n", 0, m.start()) + 1
                found.append(f"{path.relative_to(BACKEND)}:{line}")
        self.assertEqual(found, [])

    def test_templates_using_icons_load_the_tag_library(self):
        """{% load %} wird nicht vererbt: Jede Vorlage mit {% icon %} muss icons selbst laden."""
        missing = []
        for path in _templates():
            text = path.read_text(encoding="utf-8")
            if ICON_TAG.search(text) and not re.search(r"\{%\s*load\b[^%]*\bicons\b", text):
                missing.append(str(path.relative_to(BACKEND)))
        self.assertEqual(missing, [])

    def test_the_base_pages_include_the_sprite(self):
        for rel in (
            "apps/core/templates/core/base.html",
            "apps/portal/templates/portal/base.html",
            "apps/portal/templates/portal/auth_base.html",
        ):
            with self.subTest(vorlage=rel):
                self.assertIn("{% icon_sprite %}", (BACKEND / rel).read_text(encoding="utf-8"))

    def test_no_emoji_icons_are_left_in_page_templates(self):
        """Die Oberfläche nutzt SVG-Icons. Ausgenommen: E-Mails und PDFs (kein Sprite), der Meetingraum (eigene Schaltflächen-Logik) und JS-Strings."""
        emoji = re.compile("[\U0001f300-\U0001faff☀-➿⬀-⯿]️?")
        skip = ("/email/", "meeting/room.html", "pdf")
        found = []
        for path in _templates():
            rel = str(path.relative_to(BACKEND))
            if any(s in rel for s in skip):
                continue
            text = path.read_text(encoding="utf-8")
            text = re.sub(
                r"<script\b.*?</script>", "", text, flags=re.S
            )  # JS baut Tooltips mit eigenen Zeichen
            text = re.sub(r"<!--.*?-->|\{#.*?#\}", "", text, flags=re.S)
            hits = emoji.findall(text.replace("★", "").replace("☆", ""))
            if hits:
                found.append(f"{rel}: {''.join(hits)[:20]}")
        self.assertEqual(found, [], "Emojis als Icons: stattdessen {% icon %}")
