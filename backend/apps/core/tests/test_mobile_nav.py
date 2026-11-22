"""Mobilmenü (bis 1100 px): Escape schließt das offene Menü, die Überschriften der aufklappbaren Bereiche stehen wie die Links links und der Pfeil rechts.

Befunde der Live-Prüfung vom 22.11.2026: Escape tat im Mobilmenü nichts (nur die Dropdowns schlossen), und `justify-content: space-between` verteilte Symbol, Beschriftung und
Pfeil auf drei Kinder, sodass die Beschriftung in der Mitte stand. Die Wirkung im Browser prüft `scripts/browser/header-logo-regression.cjs`; diese Tests halten die Quelltexte an die Lösung.
"""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.tests.test_logo_cascade import CSS_DIR, iter_rules, split_selectors, strip_comments


class EscapeClosesTheMenuTest(TestCase):
    def test_the_menu_script_closes_the_open_menu_on_escape_and_returns_the_focus(self):
        html = self.client.get(reverse("core:login")).content.decode()
        start = html.index("Mobile Menu Toggle")
        block = html[start : html.index("Nav dropdowns", start)]

        self.assertRegex(
            block, r"event\.key === 'Escape' && navLinks\.classList\.contains\('active'\)"
        )
        self.assertRegex(block, r"closeMenu\(\);\s*menuToggle\.focus\(\);")


class DropdownHeadingAlignmentTest(SimpleTestCase):
    def narrow_rules(self):
        css = strip_comments((CSS_DIR / "shell.css").read_text(encoding="utf-8"))
        return [
            (selector, body)
            for media, prelude, body in iter_rules(css)
            if media == "(max-width: 1100px)"
            for selector in split_selectors(prelude)
        ]

    def test_the_heading_sits_next_to_its_icon_like_the_links(self):
        rules = [
            body for selector, body in self.narrow_rules() if selector == "nav .nav-dropdown-toggle"
        ]

        self.assertTrue(rules, "Regel für die Überschriften im Mobilmenü fehlt (shell.css)")
        for body in rules:
            self.assertNotIn(
                "space-between",
                body,
                "space-between verteilt Symbol, Beschriftung und Pfeil: die Beschriftung stünde in der Mitte",
            )
        self.assertTrue(any("justify-content: flex-start" in body for body in rules))

    def test_the_caret_is_pushed_to_the_right_edge(self):
        rules = [
            body
            for selector, body in self.narrow_rules()
            if selector == "nav .nav-dropdown-toggle .nav-dropdown-caret"
        ]

        self.assertTrue(rules, "Regel für den Pfeil im Mobilmenü fehlt (shell.css)")
        self.assertTrue(any("margin-left: auto" in body for body in rules))
