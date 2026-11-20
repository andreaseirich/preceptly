# Barrierefreiheit – Verbindliche Regel

**Standard:** WCAG 2.1 AA  
**Gilt für:** alle HTML-Templates im gesamten Projekt (Haupt-App + Portal)  
**Gültig ab:** 2026-06-24

---

## Regel: Bei jeder Template-Änderung prüfen

Bei **jeder** Änderung an `.html`-Dateien — auch kleinen — immer sicherstellen:

### Formulare
- Jedes `<input>`, `<select>`, `<textarea>` hat `<label for="id_feldname">`
- Pflichtfelder: `aria-required="true"`
- Fehlermeldungen: `<div id="id_feldname_errors" role="alert">` + `aria-describedby` auf dem Input
- Checkbox-Gruppen: `<fieldset><legend>`
- Submit-Buttons: explizites `type="submit"`

### Tabellen
- `<th>` in `<thead>`: `scope="col"`
- Zeilen-Header `<th>` in `<tbody>`: `scope="row"`
- Tabelle ohne `<caption>`: `aria-label="Beschreibung"`

### Navigation & Landmarks
- Neue eigenständige Seiten (ohne Base-Template): `<main id="main-content">`
- Icon-only-Buttons: `aria-label`
- Dekorative Elemente: `aria-hidden="true"`

### Dynamische Inhalte
- Ladebereich / Status-Updates: `aria-live="polite"` oder `aria-live="assertive"`
- Fehler-/Erfolgsmeldungen: `role="alert"`

### Farben
- Normaler Text: Kontrastverhältnis ≥ 4,5:1
- Großer Text (≥ 18pt / ≥ 14pt fett): ≥ 3:1
- UI-Komponenten & grafische Objekte: ≥ 3:1
- Neue Farbwerte mit Python-Skript prüfen (Formel: WCAG-Luminanz-Methode)
- Alle Farbwerte stehen in `backend/apps/core/static/core/css/tokens.css` (hell „Papier“, dunkel „Tafel“). Der Test
  `apps/core/tests/test_design_tokens.py` rechnet die Kontraste daraus nach (Text 4,5:1, Eingabe-Rand 3:1) und schlägt an,
  sobald ein Paar nicht mehr trägt. Der Textmarker-Ton (`--highlight`) ist nur Fläche hinter Tinte, nie Schriftfarbe
- Symbole sind Dekor (`{% icon %}` setzt `aria-hidden`): Wo ein Symbol allein steht, braucht der Knopf `aria-label` oder verborgenen Text

### Aufklappmenüs
- Muster „aufklappbarer Bereich“: Knopf mit `aria-expanded` und `aria-controls`, **kein** `role="menu"` ohne Pfeiltasten-Steuerung
- Aktuelle Seite im Menü mit `aria-current="page"`; Umschalter (Thema) mit `aria-pressed`

### Seitentitel
- `{% block title %}Seitenname – Preceptly{% endblock %}` — eindeutig und auf Deutsch

---

## Bereits umgesetzt (2026-06-24)

- Skip-to-Content-Link in allen Base-Templates
- `<main id="main-content">` und `<nav aria-label>` überall
- `role="alert"` auf Flash-Messages
- Vollständiger Sweep aller 42 Templates (Labels, scope, aria-*, fieldset)
- Farbkontrast-Audit: 54 Kombinationen geprüft, `#2980b9` → `#1a6fa8` korrigiert

## Überarbeitung vom 20.11.2026 (Designsystem „Kladde“)

- Eine `<h1>` je Seite (auch im Rückfalltext der Rechtsseiten und auf den Portal-Anmeldeseiten); Test `test_page_structure.py`
- Alle Felder beschriftet (`for`/`id` oder `aria-label`), auch KI-Hinweise, PDF-Upload und Kalender-Abo-Adresse
- Menü ohne `role="menu"`, Theme-Knopf mit `aria-pressed`, zweite Logo-Fassung mit `alt=""`, Sprache und Fußzeilen-Beschriftungen folgen der Anfrage
- Kalenderblöcke und Statusfarben aus Tokens (vorher weiß auf Orange 2,2:1, Gelb auf Türkis)
- Dunkles Thema und „Gerät dunkel“ liefern dieselben Werte (Test)

---

## Hintergrund

Eine Nutzerin sprach die Barrierefreiheit über Facebook an (VoiceOver/macOS).  
Der User (Andreas) hat Barrierefreiheit als dauerhaftes Qualitätsmerkmal festgelegt.  
Rückschritte durch neue Änderungen sind nicht akzeptabel.
