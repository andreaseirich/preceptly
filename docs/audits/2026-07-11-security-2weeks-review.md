# Audit-Bericht: Security-Review Feature-Änderungen 2-Wochen-Zeitraum

**Datum:** 2026-07-11
**Autor:** Fable (Security-Audit-Agent)
**Status:** Fixes ausstehend

**Umfang:** Commit-Range `2f22ea1..HEAD` (140 Commits), Fokus auf die sieben Feature-Bereiche: Portal-Auth, Meeting/WebRTC-Consumer, Datei-Uploads, Abrechnung/PDF, e-recht24-Webhook, CanonicalDomainMiddleware, Dependency-Bumps. Nur Lese-/Analysezugriff, kein Code geändert.

---

[Modell: fable]
Ich habe alle sieben Bereiche direkt im Code geprüft (kein Haiku-Unteragent nötig — für ein Security-Audit ist das direkte Lesen der Quelldateien zuverlässiger). Hier der Bericht.

---

# Sicherheits-Audit Preceptly — Feature-Änderungen 24.06.–11.07.2026

**Umfang:** Commit-Range `2f22ea1..HEAD` (140 Commits), Fokus auf die sieben genannten Feature-Bereiche. Nur Lese-/Analysezugriff, kein Code geändert.

**Gesamturteil: Keine kritischen Funde.** Die Architektur ist durchweg solide — WebSocket-Auth, IDOR-Schutz und PDF-Injection sind sauber gelöst. Es gibt **einen mittleren Fund** (unauthentifizierter Griefing/DoS über Passwort-Reset) und mehrere Härtungsempfehlungen (low). Ich habe nichts erfunden — die meisten geprüften Punkte sind tatsächlich korrekt umgesetzt.

---

## Mittlere Funde

### M1 — Passwort-Reset deaktiviert fremde Portal-Konten (unauthentifizierter Griefing/DoS)
**Datei:** `backend/apps/portal/views.py:531` (`PortalPasswordResetRequestView.post`)

Der Reset recycelt den Einladungs-Token-Mechanismus und setzt dabei **`link.is_active = False`** auf dem `StudentPortalLink`/`ParentStudentLink`. Der Login-Primärpfad (Zeile 79 ff.) prüft aber nur `django_user.is_active`, **nicht** `link.is_active` — während fast alle anderen Portal-Views (`StudentHomeView` Zeile 186, `_get_portal_student` Zeile 612 ff., Dokumente, Buchung, Kalender) ein aktives Link verlangen.

**Angriff:** Ein Angreifer kennt die E-Mail eines Schülers/Elternteils (z. B. aus einer Buchungsbestätigung) und ruft `/portal/password-reset/` auf. Ein einziger Request (Rate-Limit 5/min/IP genügt) deaktiviert das Link. Das Opfer erhält eine ungewollte Reset-Mail und sein Portal ist danach faktisch unbrauchbar (404/403 auf Home, Dokumente, Buchung), bis es den Reset-Flow durchläuft und ein neues Passwort setzt. Der Angreifer erlangt **keinen** Kontozugriff (Passwort wird nie umgangen), aber er kann die Portal-Nutzung gezielt sabotieren und einen Passwortwechsel erzwingen.

**Ursache:** Vermischung von „Konto aktiv" und „hat offenen Token". Empfehlung: Für Reset ein separates Token-Feld (z. B. `reset_token`/`reset_token_created_at`) verwenden und `is_active` unangetastet lassen — dann bleibt das Konto funktionsfähig, während der Reset-Link gültig ist. Hinweis: `PortalInviteResendView` (`students/views.py:300`) setzt ebenfalls `is_active=False`, ist aber tutor-authentifiziert und damit unkritisch.

---

## Low / Härtungsempfehlungen

### L1 — Portal-Passwörter umgehen die Django-Passwort-Validatoren
`portal/views.py:472` (Aktivierung) und `:1849` (Profil-Passwortänderung) prüfen nur `len < 8`. Die konfigurierten `AUTH_PASSWORD_VALIDATORS` (CommonPassword, NumericPassword, UserAttributeSimilarity) laufen nur für Tutor-Konten, nicht für Portal-Nutzer. Empfehlung: `django.contrib.auth.password_validation.validate_password()` in beiden Pfaden aufrufen.

### L2 — e-Recht24-Webhook ohne Rate-Limiting / Replay-Schutz
`core/views_erecht24.py` + `core/erecht24_service.py:204`. Der Secret-Vergleich per `hmac.compare_digest` und das 64-KB-Limit sind korrekt (fail-closed bei leerem Secret). Der Endpunkt hat aber **kein** Rate-Limit und keinen Nonce/Timestamp gegen Replay. Die **Auswirkung ist gering**: Ein erratenes/wiederholtes Secret erlaubt nur, ein Re-Pull der Rechtstexte von der vertrauenswürdigen e-Recht24-API auszulösen (Inhalt wird per `nh3` sanitisiert, kein Payload-Content wird gespeichert). Empfehlung dennoch: Rate-Limit (z. B. 10/min) ergänzen. Zusatz: `secret.encode()` (Zeile 204) wirft bei nicht-String-Secret im JSON eine 500 — `str(payload.get(...))` wäre robuster.

### L3 — Tutor-Upload-Pfad ohne Magic-Byte-Prüfung
`students/views.py:391-428` (`StudentDocumentListView.post`) prüft nur Endung + Größe, **nicht** `validate_file_magic`. Der Portal-Pfad (`portal/views.py:1254`) und der Meeting-Pfad (`meeting/views.py:98`) prüfen Magic Bytes korrekt. Risiko gering (Tutor lädt in eigenes Konto, Auslieferung immer als `attachment`), aber inkonsistent — dieselbe geteilte `validate_file_magic()` sollte auch hier laufen.

### L4 — Keine E-Mail-Eindeutigkeit zwischen `contract.email` und Django-User-E-Mail
`portal/views.py:79-113` (Login-Fallback + Self-Healing) und `:1816-1835` (Profil-E-Mail-Änderung). Der Duplikat-Check prüft nur `portal_profile`-User, nicht `contract.email`. Bei Legacy-Konten ohne gesetzte Django-E-Mail kann dies theoretisch zu einer Login-Kollision/Aussperrung führen (der Primärpfad löst die E-Mail eindeutig auf einen anderen User auf). Exposition begrenzt, da neue Konten die E-Mail direkt am Django-User gesetzt bekommen. Härtung: E-Mail global eindeutig validieren.

### L5 — Passwortänderung rotiert Session nicht / invalidiert andere Sessions nicht
`portal/views.py:1857`: Nach `set_password` wird nur `portal_user_id` neu gesetzt, kein `cycle_key()`, und andere aktive Portal-Sessions (Custom-Session-Auth) bleiben gültig. Low.

---

## Incidentaler Nicht-Security-Bug (fail-closed)

`PortalDocumentDownloadView` (`portal/views.py:1287`) ruft `doc.file_exists()` auf, aber `file_exists` ist eine `@property` (`students/models.py:69`) → `bool()` wird aufgerufen → `TypeError` → 500. **Portal-Dokument-Downloads sind dadurch dauerhaft defekt** (der Tutor-Pfad `students/views.py:455` nutzt korrekt `doc.file_exists` ohne Klammern). Kein Sicherheitsrisiko (schlägt geschlossen fehl, kein Datenleck), aber ein Funktionsfehler, den ihr beheben solltet: `if not doc.file_exists():` → `if not doc.file_exists:`.

---

## Was geprüft und für sicher befunden wurde

**1. Portal-Auth** — Token per `uuid.uuid4().hex` / `secrets.token_urlsafe(32)` (kryptographisch sicher, unvorhersagbar); Aktivierung invalidiert den Token korrekt (`views.py:499`); 7-Tage-Ablauf greift (`:428`). Kein Account-Takeover über die E-Mail-Login-Umstellung möglich — jeder Pfad prüft das Passwort, Einladung/Resend nutzen `select_for_update`/atomare Transaktionen gegen Races. Session-Fixation-Schutz (`cycle_key`) beim Login/Aktivierung vorhanden. Kein IDOR in der Profilbearbeitung (arbeitet nur auf dem eigenen Konto, mit Duplikat-Check). Timing-sicherer Dummy-Hash gegen Enumeration.

**2. Meeting/WebRTC-Consumer** — WS-Auth ist robust: `_load_room_and_authorize` (`consumers.py:62`) verlangt DB-seitig entweder Tutor-Eigentum oder ein aktives `StudentPortalLink`/`ParentStudentLink`. Ein nicht-autorisierter Nutzer kann **keinem** fremden Raum beitreten, selbst mit bekanntem Token. Room-Lock via `asyncio.Lock` pro Gruppe, Peer-Bereinigung race-sicher innerhalb des Locks. Relay/Kick prüfen Zielperson im Raum bzw. Tutor-Rolle. Rate-Limit (200/10s pro Verbindung) und Channel-Capacity sind **kein relevantes DoS-Risiko**, da jede Verbindung DB-authentifiziert ist und die Nachrichten-Amplifikation durch die (kleine, autorisierte) Raumbelegung begrenzt bleibt. Chat/Namen `html.escape`, Whiteboard-Felder per Whitelist gefiltert.

**3. Datei-Uploads/Storage** — Kein Path Traversal: `sanitize_doc_name` (`upload_validation.py:48`) macht `basename` + `get_valid_filename`, Django-Storage vergibt sichere Namen. Kein IDOR beim Download: Portal (`views.py:1286`), Meeting (`views.py:153`) und Tutor (`students/views.py:454`) scopen jedes Dokument per `get_object_or_404(..., session/student=<geprüftes Objekt>)`. Auslieferung als `attachment` bzw. `inline` nur für Bild/PDF mit `X-Content-Type-Options: nosniff` und restriktiver CSP. Delete-Pfade fangen fehlende Dateien ab (kein Delete-then-use-Crash). SVG/HTML nicht in der Whitelist (kein Stored-XSS über Uploads).

**4. Abrechnung/PDF** — Alle User-Eingaben (`payer_name`, `payer_address`, `issuer_*`, `item.description`, `invoice_number`) werden vor der Übergabe an ReportLab-`Paragraph` mit `html.escape` behandelt → keine Markup-/Injection-Lücke in der Mini-HTML-Interpretation von ReportLab. Alle Billing-Views scopen strikt über `Invoice.objects.filter(owner=user)` → **kein IDOR** auf fremde Rechnungen/PDFs. Download-Dateinamen gegen Header-Injection saniert (`views.py:354`, `:495`).

**5. e-Recht24-Webhook** — Aktueller Zustand (Secret-in-Payload per `compare_digest`, 64-KB-Limit, fail-closed bei leerem Secret) ist grundsätzlich korrekt gegen Brute-Force (konstante Zeit, langes Secret) — siehe L2 für die verbleibende Rate-Limit-Empfehlung.

**6. CanonicalDomainMiddleware** — **Kein Open Redirect:** Ziel-Host ist fest `https://preceptly.de`, nur der Pfad/Query (`get_full_path`) wird angehängt; Redirect nur für `www.preceptly.de` und `*.up.railway.app`. Läuft vor Session-/CSRF-Middleware und gibt früh ein 301 zurück — da Cookies domain-scoped sind, entstehen keine Cookie-/CSRF-Wechselwirkungen.

**7. Dependencies** — `Django==6.0.7`, `pillow==12.3.0`, `charset-normalizer==3.4.9`, `requests==2.34.2`, `urllib3==2.7.0`, `certifi==2026.6.17` sind aktuell; keine mir bekannten offenen CVEs, die durch die Bumps ungeschlossen blieben. Die Pygments-ReDoS (CVE-2026-4539) ist per Git-Pin bereits gehandhabt, `pip-audit` liegt in den Dev-Deps.

---

**Empfohlene Priorität:** M1 zeitnah beheben (separates Reset-Token statt `is_active=False`), danach L1 (Passwort-Validatoren) und der `file_exists()`-Funktionsbug. L2–L5 sind Härtung ohne akute Ausnutzbarkeit.

---

## Offene Punkte — Status-Übersicht

| ID | Beschreibung | Datei / Zeile | Status |
|----|--------------|---------------|--------|
| M1 | Passwort-Reset deaktiviert fremde Portal-Konten (Griefing/DoS) | `portal/views.py:531` | Fixes ausstehend |
| L1 | Portal-Passwörter umgehen Django-Passwort-Validatoren | `portal/views.py:472`, `:1849` | Fixes ausstehend |
| L2 | e-Recht24-Webhook ohne Rate-Limiting / Replay-Schutz | `core/views_erecht24.py`, `core/erecht24_service.py:204` | Fixes ausstehend |
| L3 | Tutor-Upload-Pfad ohne Magic-Byte-Prüfung | `students/views.py:391-428` | Fixes ausstehend |
| L4 | Keine E-Mail-Eindeutigkeit zwischen `contract.email` und Django-User-E-Mail | `portal/views.py:79-113`, `:1816-1835` | Fixes ausstehend |
| L5 | Passwortänderung rotiert Session nicht / invalidiert andere Sessions nicht | `portal/views.py:1857` | Fixes ausstehend |
| Bug | `file_exists()` als Property falsch aufgerufen → Portal-Downloads defekt (500) | `portal/views.py:1287`, `students/models.py:69` | Fixes ausstehend |
