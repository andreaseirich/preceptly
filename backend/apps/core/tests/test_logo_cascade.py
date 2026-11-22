"""Wächter: Die Themen-Regeln der Logo-Fassung dürfen keine Layout-Regel der Kopfzeile überstimmen.

Befund vom 22.11.2026 (Live-Prüfung): Im dunklen Thema zeigte die Kopfzeile bis 1100 px Breite Schriftzug UND Icon, und auf öffentlichen Seiten lief sie bei 390 px über
(Sprachwahl abgeschnitten). Ursache: Die Regel `:root:not([data-theme="light"]) .logo--on-dark { display: block }` im Block `prefers-color-scheme: dark` (Spezifität 0,3,0) schlug
`nav .nav-brand .logo-full { display: none }` (0,2,1, shell.css, `max-width: 1100px`). Ein Test mit gesetztem `data-theme` allein sah das nicht, weil dort `[data-theme="dark"] …` (0,2,0)
verliert; erst die Kombination „Gerät dunkel“ + schmaler Bildschirm + keine gespeicherte Themenwahl traf die Regel. Seitdem stehen die Themen-Selektoren in `:where()` (0,1,0).

Diese Tests prüfen die Kaskade am Stylesheet selbst (Spezifität und Reihenfolge). Die Wirkung im Browser prüft `scripts/browser/header-logo-regression.cjs`.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

CSS_DIR = Path(__file__).resolve().parents[1] / "static" / "core" / "css"
FUNCTIONAL = re.compile(r":(where|not|is|has)\(")


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def iter_rules(css, media=""):
    """Alle Regeln als (Medienbedingung, Selektorliste, Inhalt); verschachtelte @media-Blöcke werden aufgelöst, andere @-Regeln übersprungen."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j == -1:
            break
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            depth += css[k] == "{"
            depth -= css[k] == "}"
            k += 1
        body = css[j + 1 : k - 1]
        if prelude.startswith("@media"):
            yield from iter_rules(body, prelude[len("@media") :].strip())
        elif not prelude.startswith("@"):
            yield media, prelude, body
        i = k


def split_selectors(prelude):
    parts, depth, cur = [], 0, ""
    for ch in prelude:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return [p for p in parts if p]


def specificity(selector):
    """(a, b, c) nach CSS Selectors Level 4: :where() zählt 0, :not()/:is()/:has() zählen mit ihrem spezifischsten Argument."""
    a = b = c = 0
    rest = ""
    i = 0
    while i < len(selector):
        m = FUNCTIONAL.match(selector, i)
        if not m:
            rest += selector[i]
            i += 1
            continue
        depth, k = 1, m.end()
        while k < len(selector) and depth:
            depth += selector[k] == "("
            depth -= selector[k] == ")"
            k += 1
        if m.group(1) != "where":
            args = [specificity(x) for x in split_selectors(selector[m.end() : k - 1])]
            if args:
                ia, ib, ic = max(args)
                a, b, c = a + ia, b + ib, c + ic
        i = k
    a += len(re.findall(r"#[\w-]+", rest))
    rest = re.sub(r"#[\w-]+", " ", rest)
    b += len(re.findall(r"\[[^\]]*\]", rest))
    rest = re.sub(r"\[[^\]]*\]", " ", rest)
    b += len(re.findall(r"\.[\w-]+", rest))
    rest = re.sub(r"\.[\w-]+", " ", rest)
    c += len(re.findall(r"::[\w-]+", rest))
    rest = re.sub(r"::[\w-]+", " ", rest)
    b += len(re.findall(r":[\w-]+", rest))
    rest = re.sub(r":[\w-]+", " ", rest)
    c += len([t for t in re.split(r"[\s>+~]+", rest) if t and t != "*"])
    return (a, b, c)


def display_rules():
    """Alle Regeln, die `display` setzen: (Datei, Medienbedingung, Selektor, Spezifität, Inhalt)."""
    found = []
    for path in sorted(CSS_DIR.glob("*.css")):
        for media, prelude, body in iter_rules(strip_comments(path.read_text(encoding="utf-8"))):
            if not re.search(r"(^|[;\s])display\s*:", body):
                continue
            for selector in split_selectors(prelude):
                found.append((path.name, media, selector, specificity(selector), body))
    return found


class SpecificityHelperTest(SimpleTestCase):
    def test_the_helper_computes_the_values_the_bug_depended_on(self):
        cases = {
            "nav .nav-brand .logo-full": (0, 2, 1),
            ".logo--on-dark": (0, 1, 0),
            '[data-theme="dark"] .logo--on-dark': (0, 2, 0),
            ':root:not([data-theme="light"]) .logo--on-dark': (0, 3, 0),
            ':where([data-theme="dark"]) .logo--on-dark': (0, 1, 0),
            ':where(:root:not([data-theme="light"])) .logo--on-dark': (0, 1, 0),
            "#a .b:hover::before": (1, 2, 1),
            "a:is(.x, #y)": (1, 0, 1),
        }
        for selector, expected in cases.items():
            with self.subTest(selector=selector):
                self.assertEqual(specificity(selector), expected)


class LogoCascadeTest(SimpleTestCase):
    def variants(self):
        return [r for r in display_rules() if re.search(r"\.logo--on-(light|dark)\b", r[2])]

    def test_the_theme_rules_of_the_logo_add_no_specificity(self):
        variants = self.variants()

        self.assertGreaterEqual(
            len(variants), 5, "Basisregel, zwei Themen-Regeln, zwei Regeln für „Gerät dunkel“"
        )
        for name, media, selector, spec, _ in variants:
            with self.subTest(selector=selector, media=media):
                self.assertLessEqual(
                    spec,
                    (0, 1, 0),
                    f"{name}: `{selector}` hat Spezifität {spec}. Sie darf nicht über der von `.logo--on-dark` (0,1,0) liegen, sonst überstimmt eine Themen-Regel "
                    "die Layout-Regel, die den Schriftzug in der schmalen Kopfzeile ausblendet. Themen-Selektoren gehören in :where().",
                )

    def test_the_narrow_header_hides_the_wordmark_with_a_rule_that_beats_every_theme_rule(self):
        hide = [
            r
            for r in display_rules()
            if re.search(r"\.logo-full\b", r[2])
            and "max-width: 1100px" in r[1]
            and re.search(r"display\s*:\s*none", r[4])
        ]

        self.assertTrue(
            hide, "Die Regel, die den Schriftzug bis 1100 px ausblendet, fehlt (shell.css)"
        )
        strongest_theme_rule = max(spec for _, _, _, spec, _ in self.variants())
        for name, _media, selector, spec, _ in hide:
            self.assertGreater(
                spec,
                strongest_theme_rule,
                f"{name}: `{selector}` {spec} muss die Themen-Regeln {strongest_theme_rule} schlagen",
            )

    def test_the_icon_is_shown_by_the_same_breakpoint(self):
        icon = [
            r
            for r in display_rules()
            if re.search(r"\.logo-icon\b", r[2])
            and "max-width: 1100px" in r[1]
            and re.search(r"display\s*:\s*block", r[4])
        ]

        self.assertTrue(icon, "Bis 1100 px muss das Icon die Marke übernehmen (shell.css)")

    def test_the_dark_variant_rules_come_after_the_base_rules(self):
        # Unter gleicher Spezifität (0,1,0) entscheidet die Reihenfolge: .logo → .logo--on-dark → Thema dunkel → Gerät dunkel
        css = strip_comments((CSS_DIR / "components.css").read_text(encoding="utf-8"))
        positions = [
            css.index(".logo { "),
            css.index(".logo--on-dark { display: none; }"),
            css.index(':where([data-theme="dark"]) .logo--on-dark'),
            css.index(':where(:root:not([data-theme="light"])) .logo--on-dark'),
        ]

        self.assertEqual(positions, sorted(positions))
