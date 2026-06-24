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

### Seitentitel
- `{% block title %}Seitenname – Preceptly{% endblock %}` — eindeutig und auf Deutsch

---

## Bereits umgesetzt (2026-06-24)

- Skip-to-Content-Link in allen Base-Templates
- `<main id="main-content">` und `<nav aria-label>` überall
- `role="alert"` auf Flash-Messages
- Vollständiger Sweep aller 42 Templates (Labels, scope, aria-*, fieldset)
- Farbkontrast-Audit: 54 Kombinationen geprüft, `#2980b9` → `#1a6fa8` korrigiert

---

## Hintergrund

Eine Nutzerin sprach die Barrierefreiheit über Facebook an (VoiceOver/macOS).  
Der User (Andreas) hat Barrierefreiheit als dauerhaftes Qualitätsmerkmal festgelegt.  
Rückschritte durch neue Änderungen sind nicht akzeptabel.
