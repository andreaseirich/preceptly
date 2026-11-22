#!/usr/bin/env node
/*
 * Browser-Regressionsprüfung der Kopfzeile: Es erscheint die vorgesehene Logovariante, Sprachwahl und Navigation bleiben erreichbar, die Seite läuft nicht seitlich über.
 *
 * Hintergrund (22.11.2026): Im dunklen Thema zeigte die Kopfzeile bis 1100 px Breite Schriftzug und Icon zugleich, auf öffentlichen Seiten lief sie bei 390 px über. Die Regel für
 * „Gerät dunkel“ schlug die Regel, die den Schriftzug ausblendet. Aufgefallen ist es erst live, weil die Kombination „dunkle Geräteeinstellung + schmaler Bildschirm + keine
 * gespeicherte Themenwahl“ in keiner früheren Prüfung vorkam. Diese Matrix deckt sie ab; das Gegenstück im Test-Lauf ist apps/core/tests/test_logo_cascade.py (prüft die Kaskade am Stylesheet).
 *
 * Matrix je Seite:  Geräteeinstellung (hell, dunkel) × gespeichertes Thema (keins, hell, dunkel) × Sprache (de, en) × Breite (360, 390, 768, 1099, 1100, 1101, 1440),
 *                   dazu die Kombination ohne JavaScript (kein `data-theme`, nur die CSS-Abfrage der Geräteeinstellung).
 * Erwartung:        bis 1100 px nur das Icon in der Marke, ab 1101 px nur der Schriftzug in der Fassung des wirksamen Themas (gespeichert, sonst Geräteeinstellung);
 *                   Menüknopf nur bis 1100 px; Themenknopf, Abmelden bzw. Home/Anmelden und Sprachwahl liegen vollständig im Fenster; die Navigation ist erreichbar
 *                   (bis 1100 px nach dem Öffnen der Schublade, deren Logo ebenfalls zum Thema passt); kein seitlicher Überlauf der Seite.
 *                   In der geöffneten Schublade (bis 1100 px): Beschriftungen der aufklappbaren Bereiche neben dem Symbol, Pfeile am rechten Rand; Escape schließt das Menü und
 *                   gibt den Fokus an den Menüknopf zurück (Befunde der Live-Prüfung vom 22.11.2026).
 *
 * Aufruf:   PLAYWRIGHT_DIR=<Ordner mit node_modules/playwright-core> [CHROME_PATH=<Chrome>] \
 *           node scripts/browser/header-logo-regression.cjs --base https://beispiel.example [--paths /login/,/] [--widths 360,390] [--route modul.cjs] [--verbose]
 *   --route   Modul, das `module.exports = async (context, { base, lang }) => {…}` ausführt, um Anfragen selbst zu beantworten (zum Beispiel eine statische Spiegelung oder
 *             eine Anwendung ohne offenen Port). Sonst geht der Browser direkt an --base.
 * Es werden nur lesende Seitenaufrufe gemacht (kein Anmelden, kein Absenden); angemeldete Seiten prüft man mit --route gegen eine Instanz, die sie ohne Anmeldung ausliefert.
 * Ausgabe: Verstöße, Zusammenfassung je Fall; Beendigungscode 1 bei mindestens einem Verstoß.
 */
"use strict";
const path = require("path");

const arg = (name, fallback) => {
  const i = process.argv.indexOf("--" + name);
  if (i === -1) return fallback;
  const next = process.argv[i + 1];
  return next && !next.startsWith("--") ? next : true;
};
const BASE = String(arg("base", "")).replace(/\/$/, "");
if (!BASE) { console.error("--base fehlt"); process.exit(2); }
const PATHS = String(arg("paths", "/login/")).split(",").map((p) => p.trim()).filter(Boolean);
const WIDTHS = String(arg("widths", "360,390,768,1099,1100,1101,1440")).split(",").map(Number);
const ROUTE = arg("route", null);
const VERBOSE = !!arg("verbose", false);
const BREAKPOINT = 1100; // shell.css: @media (max-width: 1100px)
const HEIGHT = 900;
const { chromium } = require(path.join(process.env.PLAYWRIGHT_DIR || process.cwd(), "node_modules", "playwright-core"));

// Läuft im Browser: misst, was in der Kopfzeile tatsächlich zu sehen ist.
function measure() {
  const vw = document.documentElement.clientWidth;
  const shown = (e) => !!e && e.checkVisibility({ checkVisibilityCSS: true }) && e.getBoundingClientRect().width > 0;
  const inside = (e) => { const r = e.getBoundingClientRect(); return r.left >= -0.5 && r.right <= vw + 0.5; };
  const file = (img) => (img.getAttribute("src") || "").split("/").pop().replace(/\.[0-9a-f]{8,}(?=\.)/, "");
  const nav = document.querySelector("nav");
  const toggle = document.getElementById("menuToggle");
  const right = [...document.querySelectorAll("nav .nav-right button, nav .nav-right a, nav .nav-right select")].filter(shown);
  const select = document.querySelector("nav .nav-right select[name=language]");
  const links = [...document.querySelectorAll("#navLinks > a:not(.nav-links-brand), #navLinks .nav-dropdown-toggle")].filter(shown);
  // Symbol → Beschriftung und Pfeil → rechter Rand der aufklappbaren Überschriften (eine zentrierte Beschriftung ergäbe große Abstände)
  const labelGaps = [];
  const caretGaps = [];
  for (const t of [...document.querySelectorAll("#navLinks .nav-dropdown-toggle")].filter(shown)) {
    const icon = t.querySelector("svg");
    const caret = t.querySelector(".nav-dropdown-caret");
    const walker = document.createTreeWalker(t, NodeFilter.SHOW_TEXT); // ohne Rückruf: Der Browser führt ohne JavaScript keinen aus
    let text = walker.nextNode();
    while (text && !text.textContent.trim()) text = walker.nextNode();
    if (icon && text) { const r = document.createRange(); r.selectNodeContents(text); labelGaps.push(Math.round(r.getBoundingClientRect().left - icon.getBoundingClientRect().right)); }
    if (caret) caretGaps.push(Math.round(t.getBoundingClientRect().right - caret.getBoundingClientRect().right));
  }
  return {
    labelGaps,
    caretGaps,
    vw,
    theme: document.documentElement.getAttribute("data-theme"),
    brand: [...document.querySelectorAll("nav .nav-brand img")].filter(shown).map(file),
    panelLogos: [...document.querySelectorAll("nav .nav-links-brand img")].filter(shown).map(file),
    toggleShown: shown(toggle),
    expanded: toggle && toggle.getAttribute("aria-expanded"),
    rightOutside: right.filter((e) => !inside(e)).map((e) => (e.id || e.getAttribute("aria-label") || e.name || e.tagName).toString().slice(0, 30)),
    rightCount: right.length,
    selectShown: shown(select),
    selectInside: !!select && shown(select) && inside(select),
    linksCount: links.length,
    linksOutside: links.filter((e) => !inside(e)).map((e) => e.textContent.trim().replace(/\s+/g, " ").slice(0, 24)),
    overflow: document.documentElement.scrollWidth > vw + 1,
    navShown: shown(nav),
  };
}

const failures = [];
let checks = 0;
const summary = new Map();
function check(label, name, pass, detail = "") {
  checks++;
  const s = summary.get(label) || { ok: 0, bad: 0 };
  summary.set(label, s);
  if (pass) { s.ok++; if (VERBOSE) console.log(`  ✓ ${label} · ${name}`); return; }
  s.bad++;
  failures.push({ label, name, detail });
  console.log(`  ✗ ${label} · ${name}${detail ? "  → " + detail : ""}`);
}

(async () => {
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: "chrome" });
  const cases = [];
  for (const scheme of ["light", "dark"]) for (const stored of [null, "light", "dark"]) for (const lang of ["de", "en"]) cases.push({ scheme, stored, lang, js: true });
  for (const scheme of ["light", "dark"]) for (const lang of ["de", "en"]) cases.push({ scheme, stored: null, lang, js: false });

  for (const c of cases) {
    const effective = c.stored || c.scheme;
    const wordmark = effective === "dark" ? "preceptly-logo-dark.svg" : "preceptly-logo.svg";
    const context = await browser.newContext({
      viewport: { width: 1440, height: HEIGHT }, colorScheme: c.scheme, javaScriptEnabled: c.js, deviceScaleFactor: 1, locale: c.lang === "de" ? "de-DE" : "en-GB",
    });
    await context.addInitScript((stored) => {
      try {
        localStorage.setItem("beta_notice_dismissed_forever", "1"); localStorage.setItem("pwa_install_dismissed", "1"); localStorage.setItem("pwa_install_dismissed_portal", "1");
        if (stored) localStorage.setItem("theme", stored); else localStorage.removeItem("theme");
      } catch (e) { /* ohne Speicher gilt die Geräteeinstellung */ }
    }, c.stored);
    await context.addCookies([{ name: "django_language", value: c.lang, url: BASE + "/" }]);
    if (ROUTE) await require(path.resolve(String(ROUTE)))(context, { base: BASE, lang: c.lang });

    for (const p of PATHS) {
      const label = `Gerät ${c.scheme}, gespeichert ${c.stored || "keins"}, ${c.lang}${c.js ? "" : ", ohne JS"}, ${p}`;
      const page = await context.newPage();
      try {
        await page.goto(BASE + p, { waitUntil: "load" });
        await page.waitForTimeout(500);
        for (const w of WIDTHS) {
          await page.setViewportSize({ width: w, height: HEIGHT });
          await page.waitForTimeout(200);
          const m = await page.evaluate(measure);
          const narrow = w <= BREAKPOINT;
          const at = `${w}px`;
          if (c.js) check(label, `${at}: Thema im Dokument = ${effective}`, m.theme === effective, `data-theme=${m.theme}`);
          else check(label, `${at}: ohne JS kein data-theme`, m.theme === null, `data-theme=${m.theme}`);
          const expectedBrand = narrow ? ["preceptly-icon.svg"] : [wordmark];
          check(label, `${at}: Marke zeigt ${expectedBrand.join("")}`, JSON.stringify(m.brand) === JSON.stringify(expectedBrand), `sichtbar: ${m.brand.join(", ") || "nichts"}`);
          check(label, `${at}: Menüknopf ${narrow ? "sichtbar" : "ausgeblendet"}`, m.toggleShown === narrow, `sichtbar=${m.toggleShown}`);
          check(label, `${at}: Sprachwahl sichtbar und vollständig im Fenster`, m.selectInside, `sichtbar=${m.selectShown}`);
          check(label, `${at}: Themenknopf und Konto-Symbole im Fenster`, m.rightCount >= 3 && m.rightOutside.length === 0, `außerhalb: ${m.rightOutside.join(", ")} (gezählt ${m.rightCount})`);
          check(label, `${at}: kein seitlicher Überlauf der Seite`, !m.overflow);
          if (!narrow) {
            check(label, `${at}: Navigation sichtbar und im Fenster`, m.linksCount >= 1 && m.linksOutside.length === 0, `außerhalb: ${m.linksOutside.join(", ")} (gezählt ${m.linksCount})`);
          } else if (c.js) {
            await page.click("#menuToggle");
            await page.waitForTimeout(350);
            const o = await page.evaluate(measure);
            check(label, `${at}: Menü öffnet (aria-expanded)`, o.expanded === "true", `aria-expanded=${o.expanded}`);
            check(label, `${at}: Schublade: Navigation sichtbar und im Fenster`, o.linksCount >= 1 && o.linksOutside.length === 0, `außerhalb: ${o.linksOutside.join(", ")} (gezählt ${o.linksCount})`);
            check(label, `${at}: Schublade: genau ein Logo in der Fassung des Themas`, JSON.stringify(o.panelLogos) === JSON.stringify([wordmark]), `sichtbar: ${o.panelLogos.join(", ") || "nichts"}`);
            check(label, `${at}: Marke bleibt bei offener Schublade das Icon`, JSON.stringify(o.brand) === JSON.stringify(["preceptly-icon.svg"]), `sichtbar: ${o.brand.join(", ")}`);
            check(label, `${at}: Schublade: Beschriftungen der aufklappbaren Bereiche stehen neben dem Symbol`, o.labelGaps.length >= 1 && o.labelGaps.every((g) => g <= 24), `Abstand Symbol→Beschriftung: ${o.labelGaps.join(", ")} px`);
            check(label, `${at}: Schublade: Pfeile stehen am rechten Rand`, o.caretGaps.length >= 1 && o.caretGaps.every((g) => g <= 40), `Abstand Pfeil→Rand: ${o.caretGaps.join(", ")} px`);
            // Der Klick auf den Menüknopf hat diesen schon fokussiert; erst den Fokus in die Schublade setzen, sonst sagt der Fokus-Check nichts aus
            await page.evaluate(() => { const el = document.querySelector("#navLinks .nav-dropdown-toggle, #navLinks a:not(.nav-links-brand)"); if (el) el.focus(); });
            await page.keyboard.press("Escape");
            await page.waitForTimeout(350);
            const esc = await page.evaluate(() => ({ expanded: document.getElementById("menuToggle").getAttribute("aria-expanded"), focus: document.activeElement && document.activeElement.id }));
            check(label, `${at}: Escape schließt das Menü`, esc.expanded === "false", `aria-expanded=${esc.expanded}`);
            check(label, `${at}: Escape gibt den Fokus an den Menüknopf zurück`, esc.focus === "menuToggle", `Fokus auf: ${esc.focus || "nichts"}`);
            if (esc.expanded === "false") { await page.click("#menuToggle"); await page.waitForTimeout(350); } // wieder öffnen, damit der Klick auf den Hintergrund-Layer geprüft wird
            await page.mouse.click(Math.max(w - 8, 4), HEIGHT - 20); // Klick auf den Hintergrund-Layer schließt das Menü
            await page.waitForTimeout(350);
            const cl = await page.evaluate(measure);
            check(label, `${at}: Menü schließt wieder`, cl.expanded === "false", `aria-expanded=${cl.expanded}`);
          }
        }
      } catch (e) {
        check(label, "Seite messbar", false, String(e).split("\n")[0].slice(0, 160));
      }
      await page.close();
    }
    await context.close();
  }
  await browser.close();

  console.log("\nZusammenfassung je Fall (bestanden / Verstöße):");
  for (const [label, s] of summary) console.log(`  ${s.bad ? "✗" : "✓"} ${label}: ${s.ok} / ${s.bad}`);
  console.log(`\n${checks} Prüfungen, ${failures.length} Verstöße in ${[...summary.values()].filter((s) => s.bad).length} von ${summary.size} Fällen`);
  process.exit(failures.length ? 1 : 0);
})().catch((e) => { console.error("ABBRUCH", e); process.exit(2); });
