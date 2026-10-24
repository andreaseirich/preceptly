# Institut: Standard-Stundensatz und Standard-Einheitsdauer

**Stand:** 24.10.2026 · Auftrag von Andreas: „Beim Erstellen eines Schülers soll der Stundensatz automatisch gewählt
werden, wenn man ein Institut wählt.“ und „Auch die Einheitsdauer soll dem Institut entsprechend eingestellt werden.“

## Verhalten

Beim Anlegen eines Schülers (Seiten „Neuer Schüler“ unter Verträgen und unter Schülern) füllt Preceptly **Stundensatz**
und **Einheitsdauer** aus dem gewählten Institut, sobald man es auswählt.

- Beide Werte kann man danach ändern. **Was der Tutor selbst getippt hat, bleibt** beim Wechsel des Instituts stehen.
- Ein **automatisch** eingetragener Wert wird zurückgesetzt (auf den Wert beim Laden der Seite, also leer beziehungsweise 60),
  wenn das neu gewählte Institut dafür nichts vorgibt oder „Kein Institut“ gewählt wird. So bleibt kein Wert des vorigen
  Instituts stehen.
- **Nur bei neuen Schülern.** Beim Bearbeiten und nach einem Formularfehler (abgeschicktes Formular) wird nichts ersetzt.
  Bestehende Schüler ändern sich nie, auch nicht, wenn man den Standard eines Instituts später ändert.
- Der Server überschreibt nichts: Gespeichert wird, was im Formular steht.
- Für Screenreader meldet ein Hinweis („Stundensatz und Einheitsdauer wurden aus dem Institut übernommen. Du kannst sie
  ändern.“), wenn Werte eingetragen wurden (`role="status"`). Unter den beiden Feldern steht ein Hilfetext.

## Woher die Werte kommen

Ein Institut hatte bisher weder Stundensatz noch Einheitsdauer, nur Staffeln. Neu sind zwei **optionale** Felder am Institut
(Institut bearbeiten → „Standard für neue Schüler“):

| Feld | Grenzen | Leer |
|---|---|---|
| `default_hourly_rate` (Standard-Stundensatz) | ab 0,01 € | Es gilt der Satz der **ersten Staffel** (niedrigste „ab Stunden“), unabhängig von der Reihenfolge der Einträge. Ein Satz von 0 oder eine kaputte Staffel ergibt: nichts vorbelegen |
| `default_unit_duration_minutes` (Standard-Einheitsdauer) | 1 bis 480 Minuten | Nichts vorbelegen, es bleiben die üblichen 60 |

Die Institut-Liste zeigt den Standard unter den Staffeln („Standard für neue Schüler: 14,00 €/h, 45 min“).

**Bei Instituten mit Staffeln** rechnet Preceptly nach den Staffeln ab; der Stundensatz des Schülers ist dort nur ein
Vorschlag (Pflichtfeld). Die Einheitsdauer des Schülers zählt dagegen bei der Abrechnung ohne Staffeln und für Privatschüler.

## Code

| Teil | Ort |
|---|---|
| Felder und `Institute.student_defaults()` | `apps/contracts/models.py`, Migration `0023_institute_student_defaults` (nullbar, keine Datenänderung) |
| Formulare (`InstituteForm`, `ContractForm._setup_institute_defaults`) | `apps/contracts/forms.py` |
| Skript | `apps/core/static/js/institute-defaults.js` |
| Einbau in beide Schüler-Formulare | `apps/contracts/templates/contracts/_institute_defaults.html` |
| Institut-Formular und Liste | `institute_form.html`, `institute_list.html` |
| Tests | `apps/contracts/test_institute_defaults.py` (23); das Skript wurde zusätzlich in Headless-Chrome gegen beide echten Seiten geprüft |

## Nicht geändert

Kein Wechsel des Satzes für bestehende Schüler, keine Vorbelegung beim Bearbeiten, keine Auswirkung auf Rechnungen.
