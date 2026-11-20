"""Das Designsystem „Kladde“ (core/css/tokens.css) bleibt lesbar: Kontraste nach WCAG 2.1 AA, in beiden Themen.

Die Farbwerte stehen an einer Stelle (tokens.css); die Tests lesen sie von dort und rechnen den Kontrast nach, statt die Zahlen zu wiederholen.
Wer eine Farbe ändert, sieht hier sofort, welches Paar nicht mehr trägt. Außerdem:
- die Tafel-Werte (dunkel) müssen im Block für „Gerät ist dunkel, nichts gespeichert“ dieselben sein wie bei data-theme="dark",
- die mitgelieferten Schriften müssen als Datei vorhanden sein (sonst fiele die Seite still auf Systemschrift zurück),
- die alten Token-Namen bleiben bestehen, weil Vorlagen mit eigenem CSS sie noch benutzen.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STATIC = Path(settings.BASE_DIR) / "apps/core/static"
TOKENS = (STATIC / "core/css/tokens.css").read_text(encoding="utf-8")

PAGE, CARD, SUNK = "paper-page", "paper-card", "paper-sunk"
SURFACES = (PAGE, CARD, SUNK)


def _tokens(block):
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", block))


def _themes():
    light = re.search(r":root\s*\{(.*?)\n\}", TOKENS, re.S).group(1)
    dark = re.search(r'\[data-theme="dark"\]\s*\{(.*?)\n\}', TOKENS, re.S).group(1)
    auto_dark = re.search(
        r'@media \(prefers-color-scheme: dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)\s*\{(.*?)\n  \}',
        TOKENS,
        re.S,
    ).group(1)
    return _tokens(light), _tokens(dark), _tokens(auto_dark)


LIGHT, DARK, AUTO_DARK = _themes()


def _luminance(hex_color):
    h = hex_color.strip().lstrip("#")
    chans = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _theme(name):
    # Dunkel erbt alles, was es nicht selbst setzt, vom hellen Thema (zum Beispiel --info-Abstufungen)
    return {**LIGHT, **DARK} if name == "dark" else LIGHT


# (Vordergrund, Hintergründe, Mindestverhältnis)
TEXT_ON_SURFACES = [
    "ink",
    "ink-soft",
    "accent",
    "accent-hover",
    "danger",
    "success",
    "warning",
    "info",
]


class TextContrastTest(SimpleTestCase):
    def test_text_colours_reach_aa_on_every_paper_surface(self):
        for theme in ("light", "dark"):
            tokens = _theme(theme)
            for fg in TEXT_ON_SURFACES:
                for bg in SURFACES:
                    with self.subTest(theme=theme, text=fg, grund=bg):
                        self.assertGreaterEqual(_contrast(tokens[fg], tokens[bg]), 4.5)

    def test_text_on_filled_surfaces_reaches_aa(self):
        pairs = [
            ("on-accent", "accent"),
            ("on-accent", "accent-hover"),
            ("on-success", "success"),
            ("on-highlight", "highlight"),
        ]
        for theme in ("light", "dark"):
            tokens = _theme(theme)
            for fg, bg in pairs:
                with self.subTest(theme=theme, text=fg, flaeche=bg):
                    self.assertGreaterEqual(_contrast(tokens[fg], tokens[bg]), 4.5)

    def test_text_on_status_tints_reaches_aa(self):
        """Hinweiskästen: Tinte auf der getönten Fläche. Die Tönungen sind in der Tafel halbtransparent, dort zählt die Karte darunter."""
        for theme, tokens in (("light", _theme("light")),):
            for tint in ("success-tint", "warning-tint", "danger-tint", "info-tint", "accent-tint"):
                with self.subTest(theme=theme, tint=tint):
                    self.assertGreaterEqual(_contrast(tokens["ink"], tokens[tint]), 4.5)

    def test_input_borders_reach_three_to_one(self):
        """WCAG 1.4.11: Rand von Eingabefeldern gegen den Grund."""
        for theme in ("light", "dark"):
            tokens = _theme(theme)
            with self.subTest(theme=theme):
                self.assertGreaterEqual(_contrast(tokens["line-strong"], tokens[CARD]), 3.0)

    def test_rating_stars_are_readable_on_the_card(self):
        for theme in ("light", "dark"):
            tokens = _theme(theme)
            with self.subTest(theme=theme):
                self.assertGreaterEqual(_contrast(tokens["marker"], tokens[CARD]), 4.5)

    def test_highlighter_is_only_used_behind_ink(self):
        """Der Textmarker-Ton ist Fläche, nie Schriftfarbe: gegen die Karte hätte er zu wenig Kontrast als Text."""
        css = "".join(p.read_text(encoding="utf-8") for p in (STATIC / "core/css").glob("*.css"))
        as_text = re.findall(r"[^-\w]color:\s*var\(--highlight\)", css)
        self.assertEqual(as_text, [], "--highlight nur als background, nie als color")


class ThemeConsistencyTest(SimpleTestCase):
    def test_automatic_dark_block_matches_the_explicit_dark_block(self):
        """Wer ohne gespeicherte Wahl ein dunkles Gerät hat, sieht dieselbe Tafel wie bei data-theme="dark"."""
        self.assertTrue(AUTO_DARK)
        for name in AUTO_DARK:
            with self.subTest(token=name):
                self.assertEqual(AUTO_DARK[name], DARK.get(name), name)

    def test_dark_theme_overrides_every_surface_and_text_token(self):
        for name in (
            PAGE,
            CARD,
            SUNK,
            "line",
            "line-strong",
            "ink",
            "ink-soft",
            "accent",
            "on-accent",
            "danger",
            "success",
            "warning",
            "info",
        ):
            with self.subTest(token=name):
                self.assertIn(name, DARK)

    def test_legacy_token_names_still_exist(self):
        """Vorlagen mit eigenem CSS benutzen --bg-primary, --text-primary, --border-color usw. weiter."""
        for name in (
            "bg-primary",
            "bg-secondary",
            "text-primary",
            "text-secondary",
            "border-color",
            "accent",
            "accent-hover",
            "table-header-bg",
            "input-border",
        ):
            with self.subTest(token=name):
                self.assertIn(name, LIGHT)


class FontFilesTest(SimpleTestCase):
    def test_every_font_file_named_in_tokens_css_exists(self):
        files = re.findall(r'url\("\.\./\.\./(fonts/[^"]+)"\)', TOKENS)
        self.assertGreaterEqual(len(files), 2)
        for rel in files:
            with self.subTest(datei=rel):
                self.assertTrue((STATIC / rel).is_file(), rel)

    def test_licence_texts_ship_with_the_fonts(self):
        text = (STATIC / "fonts/LICENSES.md").read_text(encoding="utf-8")
        self.assertIn("SIL Open Font License", text)
        self.assertIn("Lucide", text)
