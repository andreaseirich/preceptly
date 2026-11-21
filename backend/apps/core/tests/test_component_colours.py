"""Farben und Verhalten wichtiger Komponenten, so wie sie tatsächlich gerendert werden (Messung mit contrast.js, 21.11.2026).

Der Tokentest (`test_design_tokens`) rechnet nur die Paare aus tokens.css nach. Die Messung der gerenderten Seiten fand darüber hinaus: Ränder der Sprachwahl und der
Listenfilter mit 1,4:1, feste Farben in einzelnen Vorlagen (Grün #28a745, Rot #dc3545, Grau #6c757d …), weiße Schrift auf dem hellen Rot des dunklen Themas und eine
Fokus-Anzeige auf der Fußzeile mit 2,2:1. Diese Tests halten die Korrekturen fest; die mobilen Tabellen (nur die Tabelle scrollt, Aktionen bleiben erreichbar) gleich mit.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

APPS = Path(settings.BASE_DIR) / "apps"
CSS = APPS / "core/static/core"


def css(name):
    return (CSS / name).read_text(encoding="utf-8")


def media_block(text, query):
    """Inhalt ALLER @media-Blöcke mit dieser Bedingung (es gibt mehrere; Klammern werden gezählt)."""
    parts = []
    for match in re.finditer(re.escape(f"@media ({query})"), text):
        depth, i = 0, text.index("{", match.start())
        for j in range(i, len(text)):
            depth += text[j] == "{"
            depth -= text[j] == "}"
            if depth == 0:
                parts.append(text[i + 1 : j])
                break
    assert parts, query
    return "\n".join(parts)


class ControlBorderTest(SimpleTestCase):
    def test_the_language_choice_has_a_border_that_reaches_three_to_one(self):
        shell = css("css/shell.css")

        self.assertRegex(
            shell, r"select\.lang-select,\s*\.lang-select \{[^}]*border-color: var\(--line-strong\)"
        )

    def test_list_filters_use_the_control_border_token(self):
        text = css("list-tools.css")
        rule = re.search(r"\.list-filter input, \.list-filter select \{[^}]*\}", text).group(0)

        self.assertIn("var(--input-border)", rule)
        self.assertNotIn("var(--border-color)", rule)

    def test_the_sort_marker_is_not_dimmed(self):
        text = css("list-tools.css")

        self.assertNotRegex(text, r"\.sort-mark\s*\{[^}]*opacity:\s*0?\.[0-9]+")


class FocusAndDangerTest(SimpleTestCase):
    def test_links_in_the_dark_footer_get_a_light_focus_outline(self):
        self.assertIn(
            ".site-footer :focus-visible { outline-color: var(--footer-ink); }",
            css("css/shell.css"),
        )

    def test_danger_buttons_use_the_text_token_for_filled_danger(self):
        components = css("css/components.css")

        self.assertIn(
            ".btn-danger { background: var(--danger); color: var(--on-danger); }", components
        )
        self.assertNotRegex(components, r"\.btn-danger[^{]*\{[^}]*color:\s*#fff")

    def test_every_theme_defines_the_text_token_for_danger(self):
        tokens = css("css/tokens.css")

        self.assertEqual(
            len(re.findall(r"--on-danger:", tokens)), 3, "hell, dunkel und „Gerät dunkel“"
        )


class MobileTablesTest(SimpleTestCase):
    def setUp(self):
        self.components = css("css/components.css")

    def test_only_the_table_scrolls_sideways_on_tablets_and_phones(self):
        block = media_block(self.components, "max-width: 820px")

        self.assertRegex(block, r"table \{[^}]*display: block;")
        self.assertRegex(block, r"table \{[^}]*overflow-x: auto;")
        self.assertIn(
            "overscroll-behavior-x: contain",
            block,
            "ein Wischen am Tabellenrand schiebt nicht die ganze Seite",
        )

    def test_edge_shadows_show_that_more_columns_exist(self):
        block = media_block(self.components, "max-width: 820px")

        self.assertEqual(
            block.count("no-repeat local"),
            2,
            "Kartenfarbe verdeckt den Schatten am jeweiligen Anfang bzw. Ende",
        )
        self.assertEqual(
            block.count("no-repeat scroll"), 2, "die eigentlichen Schatten an beiden Rändern"
        )

    def test_the_action_column_stays_in_view_on_phones(self):
        block = media_block(self.components, "max-width: 640px")

        self.assertIn("table:has(.table-actions) tr > :last-child", block)
        self.assertRegex(block, r"tr > :last-child \{[^}]*position: sticky;[^}]*right: 0;")
        self.assertRegex(
            block,
            r"\.table-actions \{[^}]*flex-direction: column",
            "die Knöpfe stehen untereinander und machen die Spalte schmal",
        )

    def test_portal_tables_are_only_clipped_when_they_are_not_scrollers(self):
        portal = css("css/portal-shell.css")

        self.assertNotRegex(
            re.sub(r"@media \(min-width: 821px\) \{[^}]*\{[^}]*\}[^}]*\}", "", portal),
            r"\.portal table \{[^}]*overflow: hidden",
        )


# Feste Farben, die in der Messung unter dem Grenzwert lagen. In Seitenvorlagen gehören dort Tokens hin (var(--success), var(--danger), var(--ink-soft) …).
# (#ffeb3b steht nur im JavaScript-Tooltip der Wochenansicht auf dunklem Grund und ist dort gut lesbar)
BAD_TEXT_COLOURS = ("#28a745", "#16a34a", "#dc3545", "#6c757d", "#4a9eff", "#d97706", "#f59e0b")
BAD_FILLS = ("#27ae60", "#16a34a", "#28a745", "#ff9800", "#dc3545")
# Eigene Gerüste mit Inline-CSS, die bewusst nicht Teil der Überarbeitung sind: E-Mails, Rechnungsdokument/PDF, Meetingraum
SKIP = ("/email/", "invoice_document", "meeting/room.html", "pdf")


class NoKnownLowContrastColoursTest(SimpleTestCase):
    def templates(self):
        for path in list((APPS).rglob("*.html")) + list(
            (Path(settings.BASE_DIR) / "templates").rglob("*.html")
        ):
            rel = str(path)
            if not any(s in rel for s in SKIP):
                yield path, path.read_text(encoding="utf-8")

    def test_no_hard_coded_text_colour_that_failed_the_measurement(self):
        pattern = re.compile(
            r"(?<![-\w])color\s*:\s*(" + "|".join(BAD_TEXT_COLOURS) + r")\b", re.IGNORECASE
        )
        found = []
        for path, text in self.templates():
            found += [
                f"{path.relative_to(APPS.parent)}: {m.group(0)}" for m in pattern.finditer(text)
            ]
        self.assertEqual(
            found,
            [],
            "stattdessen var(--success), var(--danger), var(--ink-soft), var(--warning), var(--accent)",
        )

    def test_no_hard_coded_fill_with_white_text(self):
        pattern = re.compile(
            r"background(?:-color)?\s*:\s*("
            + "|".join(BAD_FILLS)
            + r")\b[^;}\"]*[;}\"]\s*[^}\"]*?color\s*:\s*(?:white|#fff\b|#ffffff)",
            re.IGNORECASE | re.DOTALL,
        )
        found = []
        for path, text in self.templates():
            found += [
                f"{path.relative_to(APPS.parent)}: {m.group(0)[:70]!r}"
                for m in pattern.finditer(text)
            ]
        self.assertEqual(
            found,
            [],
            "stattdessen var(--success)/var(--danger) mit var(--on-success)/var(--on-danger)",
        )
