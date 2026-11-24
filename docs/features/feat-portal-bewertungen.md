# Bewertungen von Eltern und Schülern (Portal)

**Status:** umgesetzt und getestet am 24.11.2026, **nicht veröffentlicht** (Freigabe von Andreas steht aus). Entscheidungen von Andreas (24.11.2026): Eltern ja, Schüler nur wenn volljährig, Einwilligung als Pflichtkästchen,
Vorname plus Rolle, bestehende Moderation, eigener Abschnitt „Stimmen von Eltern und Schülern“ auf der Startseite, Portal bleibt deutsch.

## Ziel

Eltern und Schüler erleben die Terminbuchung über Preceptly selbst. Ihre Sicht („wie viel einfacher ist es, Termine beim Tutor zu machen“) ist für neue Tutoren aussagekräftig. Bisher können nur Tutoren Preceptly bewerten
(`Review`, Tutor-Dashboard, Moderation, Startseite „aus … Bewertungen von Nachhilfelehrern“).

## Regeln

| Thema | Regel |
|---|---|
| Wer darf bewerten | Portal-Konten mit der Rolle **Elternteil**. Konten der Rolle **Schüler** nur, wenn **alle** mit ihnen verknüpften Verträge `is_adult` sind. Minderjährige Schüler sehen nichts davon. |
| Wo | Im Portal-Dashboard (`portal:student_home`, `portal:parent_home`) eine Karte „Wie einfach ist die Terminbuchung?“ mit Sternen (1 bis 5, Pflicht), freiem Kommentar (optional, höchstens 1000 Zeichen) und Anzeigename. Es gibt eine Bewertung je Konto. |
| Anzeigename | Wird beim Bewerten **eingegeben** (Pflicht, 2 bis 30 Zeichen, ohne `@` und ohne Adressen). Portal-Konten haben keinen Vornamen (Benutzername `portal_<Nr>_<Zufall>`, E-Mail), deshalb werden **nie** Benutzername oder E-Mail angezeigt. |
| Einwilligung | Pflichtkästchen: „Ich willige ein, dass mein Vorname und meine Bewertung öffentlich auf der Startseite von preceptly.de angezeigt werden. Ich kann das jederzeit mit ‚Bewertung zurückziehen‘ widerrufen.“ Ohne Einwilligung wird nichts gespeichert. Der Zeitpunkt wird festgehalten (`publish_consent_at`, Nachweis nach Art. 7 Abs. 1 DSGVO). |
| Widerruf | „Bewertung zurückziehen“ im Portal löscht die Bewertung sofort und vollständig. Löscht der Tutor das Konto oder den Vertrag, entfällt sie mit (Fremdschlüssel `CASCADE`). |
| Moderation | Wie bisher nie automatisch öffentlich. Familien-Bewertungen werden auf der Moderationsseite mit Herkunft, Anzeigename und Einwilligung gezeigt. **Freigeben geht nur mit Einwilligung und Anzeigename.** Wer die Bewertung bearbeitet, setzt die Freigabe zurück (wie bisher). |
| Anzeige | Eigener Abschnitt „Stimmen von Eltern und Schülern“ auf der Startseite: Sterne, Kommentar, „— Anna, Elternteil“ beziehungsweise „— Max, Schüler“. Nur freigegebene Bewertungen mit Einwilligung und Kommentar. Kein Durchschnitt und keine Anzahl (zu wenig Stimmen, würde zu viel versprechen). Abschnitt fehlt, solange es keine gibt. |
| Tutor-Zahlen | Durchschnitt und Anzahl „aus … Bewertungen von Nachhilfelehrern“ zählen **nur** Tutor-Bewertungen. Familien-Bewertungen fließen nicht ein. |
| Sprache | Das Portal bleibt deutsch (feste deutsche Texte). Der neue Abschnitt der Startseite ist übersetzt (englische Quelltexte, deutsche Fassung im Katalog); der Kommentar steht so, wie er geschrieben wurde. |

## Technik

- `core.Review` bekommt `source` (`tutor`, `parent`, `student`; Standard `tutor`, damit alle bisherigen Bewertungen Tutor-Bewertungen bleiben), `display_name` (leer bei Tutoren) und `publish_consent_at` (leer, wenn nicht erteilt). Additive Migration ohne Datenänderung.
- `apps/portal/reviews.py`: Berechtigung (`can_review`), Karte (`review_card`) und Formular (`PortalReviewForm`).
- Portal-Ansichten `PortalReviewView` (anlegen und aktualisieren) und `PortalReviewWithdrawView` (zurückziehen), Anmeldung über `get_portal_user` (Sitzung), Weiterleitung auf `portal:home`. Karte in `portal/_review_card.html`, eingebunden in beide Startseiten.
- Startseite: `LandingView` trennt `approved_reviews` (Tutoren, Zahlen) und `family_reviews`.
- Moderation: `moderate_review` verweigert die Freigabe ohne Einwilligung oder Anzeigenamen; die Vorlage zeigt Herkunft, Anzeigename und Einwilligung.

## Datenschutz (offen, Entscheidung bei Andreas)

Die Datenschutzerklärung entsteht aus dem eRecht24-Generator und den Overrides (`legal_overrides.py`). Sie sollte die Verarbeitung nennen: Zweck (öffentliche Bewertungen auf der Startseite), Daten (Anzeigename, Bewertung, Kommentar, Zeitpunkt der Einwilligung),
Rechtsgrundlage (Einwilligung, Art. 6 Abs. 1 lit. a DSGVO), Widerruf im Portal, Speicherdauer (bis zum Widerruf oder zur Löschung des Kontos). Das ist **nicht** Teil dieser Umsetzung und wird nicht ohne Freigabe geändert. Bis dahin steht die Information im Einwilligungstext der Karte.

## Prüfung (24.11.2026)

- 35 neue Tests (`apps/portal/test_portal_reviews.py`, `apps/core/tests/test_family_reviews.py`); sie schlugen vor der Umsetzung fehl. Mutationstest: 14 eingebaute Fehler (Berechtigung, Einwilligung, Anzeigename, Freigabe, Tutor-Zahlen, Zurückziehen, Startseite), alle gefangen.
- Regression: `apps.core` und `apps.portal` zusammen 1030 Tests OK. `makemigrations --check` sauber (Migration `0037_review_family_fields`, nur drei neue Felder mit Standardwerten).
- Sichtprüfung der gerenderten Seiten (Portal-Karte ohne und mit Bewertung, hell, dunkel und mobil; Startseite deutsch und englisch; Moderation). Eine Prüfung im Browser gegen die laufende Anwendung steht bis zur Veröffentlichung aus.

## Abnahme

Tests (Portal und Startseite) decken ab: Berechtigung je Rolle und Alter, Pflichtfelder und Einwilligung, Anzeigename-Regeln, Aktualisieren setzt die Freigabe zurück, Zurückziehen löscht nur die eigene Bewertung, Moderation ohne Einwilligung, Startseite zeigt nur freigegebene
Familien-Bewertungen mit Name und Rolle (nie Benutzername oder E-Mail) und lässt die Tutor-Zahlen unberührt. Kein Test darf eine E-Mail versenden.
