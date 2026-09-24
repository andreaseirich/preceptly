# CLAUDE.md – Preceptly

**Stand:** 24.09.2026

## Projekt-Übersicht

Preceptly ist eine Django-Webanwendung für selbständige Tutoren: Schüler und
Verträge, Stunden und Serien, Rechnungen und Einnahmen, ein Portal für Schüler
und Eltern, Video-Meetings und KI-gestützte Unterrichtsplanung.
Produktbeschreibung und Tarife: **`PRD.md`**.

Live: https://preceptly.de (Railway). Das Repository ist **öffentlich** —
keine Zugangsdaten, Schwachstellen-Listen oder Infrastruktur-Details einchecken.

## Tech-Stack

| Bereich | Technik |
|---|---|
| Backend | Django 6.1, Python 3.12 |
| Server | Daphne (ASGI) — nötig für WebSockets der Meeting-Räume |
| Echtzeit | Django Channels, Channel-Layer über Redis |
| Datenbank | PostgreSQL (Produktion), SQLite (lokal/Tests) |
| Cache | Redis (Rate-Limits, Sperren, CSP-Meldungen) |
| Frontend | Django-Templates mit eigenem CSS (kein Tailwind), wenig Vanilla-JS |
| Statische Dateien | WhiteNoise, pdf.js selbst ausgeliefert |
| Zahlungen | Stripe — nur für die Abos der Tutoren |
| Video | WebRTC, eigener TURN-Server (coturn) mit kurzlebigen Zugangsdaten |
| KI | Selbst gehostetes Sprachmodell über Tailscale, Mock-Modus ohne Schlüssel |
| Deployment | Docker, Railway (wartet auf grüne CI) |
| Qualität | Ruff, Django-Testsuite (~960 Tests), CodeQL, Dependabot |

## Repo-Struktur

```
backend/
  tutorflow/          # Projektkonfiguration (settings.py, urls.py, asgi.py)
  apps/
    core/             # Auth, Dashboard, Einstellungen, Einnahmen/EÜR, Stripe,
                      # Rechtstexte, PWA/Push, CSP, Zugriffsprotokoll
    students/         # Schülerverwaltung (auf Basis von Contract), Dokumente, Portal-Einladung
    contracts/        # Verträge und Institute
    lessons/          # Stunden, Serien, Kalender, Konflikte, öffentliche Buchung
    blocked_times/    # Sperrzeiten
    lesson_plans/     # Gespeicherte Unterrichtspläne
    ai/               # KI-Generierung (inkl. PDF-/Text-Kontext, PII-Schwärzung)
    billing/          # Rechnungen, PDF, Zahlungsstatus
    portal/           # Schüler-/Eltern-Portal
    meeting/          # Video-Meeting-Räume (WebRTC), TURN-Zugangsdaten
    calendar_sync/    # iCloud-Kalender (CalDAV)
  templates/          # Rechtstexte, Partials (Footer), Fehlerseiten
  locale/de/          # Deutsche Übersetzungen (Quelltexte englisch)
docs/
  features/           # Feature-Spezifikationen
  operations/         # Betrieb: Umgebungsvariablen, TURN, CSP
  audits/             # Prüfberichte mit Nachverfolgung
scripts/              # Hygiene-Check, Git-Hooks einrichten, Entrypoint
```

## URL-Struktur (Überblick)

| Prefix | App |
|--------|-----|
| `/` | core (Landing, Dashboard, Auth, Einstellungen, Rechtstexte) |
| `/students/` | students |
| `/contracts/` | contracts |
| `/lessons/` | lessons (inkl. öffentliche Buchung) |
| `/lesson-plans/` | lesson_plans |
| `/blocked-times/` | blocked_times |
| `/billing/` | billing |
| `/ai/` | ai |
| `/portal/` | portal |
| `/meetings/` | meeting |
| `/calendar-sync/` | calendar_sync |

## Tests ausführen

```bash
cd backend && MOCK_LLM=1 SECRET_KEY=test-ci-secret TURN_CREDENTIAL=dummy \
  ALLOWED_HOSTS=localhost,127.0.0.1 DJANGO_SETTINGS_MODULE=tutorflow.settings \
  DJANGO_DEBUG=False SECURE_SSL_REDIRECT=False python3 manage.py test apps.<modul>
```

Die volle Suite läuft im pre-push-Hook (`scripts/setup_local_git.sh` richtet
ihn ein) und in der CI. Branch-Schutz auf `main`: Checks `test` und `hygiene`
müssen grün sein.

## Konventionen

- Englische Commit-Messages (Conventional Commits: feat/fix/docs/chore/refactor)
- Ruff für Linting (`ruff check backend/apps backend/tutorflow`)
- Migrationen immer committen
- Übersetzungen: englische `msgid`, deutsche `msgstr` in `locale/de/`; danach `compilemessages`
- Echte Unicode-Zeichen: ä, ö, ü, ß — nicht ae, oe, ue, ss
- Keine „God-Files": lieber mehrere kleine, klar benannte Module
- Dateinamen mit `credentials` blockiert der Hygiene-Check (Schutz vor Schlüsseldateien)
- **Vorlagen:** jedes `<script>` mit `nonce="{{ csp_nonce }}"`; **keine** Inline-Handler
  (`onclick=…`, `onsubmit=…`, `href="javascript:…"`) — stattdessen `data-click` &
  Co. aus `apps/core/static/js/actions.js`. Ein Wächter-Test erzwingt beides.
  Details: `docs/operations/content-security-policy.md`

## Sicherheit

- Rate-Limits zählen pro Besucher über die echte Client-IP (`RATELIMIT_IP_META_KEY`)
- Content-Security-Policy im Melde-Modus: `docs/operations/content-security-policy.md`
- TURN-Zugangsdaten verfallen nach 8 Stunden: `docs/operations/turn-server.md`
- Alle Umgebungsvariablen: `docs/operations/railway-env-vars.md`

## Barrierefreiheit

Bei **jeder** Template-Änderung WCAG 2.1 AA einhalten. Verbindliche Regeln:
**`docs/ACCESSIBILITY.md`**
