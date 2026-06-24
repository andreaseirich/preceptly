# CLAUDE.md – Preceptly / TutorFlow

## Projekt-Übersicht

Preceptly (ehemals TutorFlow) ist eine Django-Webanwendung für selbständige Tutoren zur Verwaltung von Schülern, Verträgen, Stunden, Abrechnung und KI-gestützter Unterrichtsplanung.

## Tech-Stack

- **Backend:** Django 5.x, Python 3.12
- **Datenbank:** PostgreSQL (Produktion), SQLite (lokal)
- **Frontend:** Django-Templates, Tailwind CSS (via CDN)
- **Deployment:** Docker, Railway
- **Linter:** Ruff

## Repo-Struktur

```
backend/
  tutorflow/          # Django-Projektkonfiguration (settings.py, urls.py)
  apps/
    core/             # Tutor-Auth, Dashboard, Stripe
    students/         # Schülerverwaltung
    contracts/        # Verträge
    lessons/          # Stunden, Sessions
    lesson_plans/     # KI-Unterrichtspläne
    blocked_times/    # Sperrzeiten
    billing/          # Abrechnung
    ai/               # KI-Funktionen
    portal/           # Eltern/Schüler-Portal (neu)
docs/
  features/           # Feature-Spezifikationen
```

## URL-Struktur (Überblick)

| Prefix | App |
|--------|-----|
| `/` | core (Dashboard, Auth) |
| `/students/` | students |
| `/contracts/` | contracts |
| `/lessons/` | lessons |
| `/lesson-plans/` | lesson_plans |
| `/blocked-times/` | blocked_times |
| `/billing/` | billing |
| `/ai/` | ai |
| `/portal/` | portal |
| `/stripe/` | core (Stripe-Integration) |

## Portal-App (apps.portal)

- URL-Prefix: `/portal/`
- Login: `/portal/login/` (separate Seite für Eltern/Schüler)
- Modelle: `PortalUser`, `StudentPortalLink`, `ParentStudentLink`, `ProgressNote`, `PortalMessage`
- Neue Felder: `Session.homework`, `Session.meeting_url`
- Doku: `docs/features/feat-portal.md`
- Implementierungsplan: `PORTAL_PLAN.md`

## Konventionen

- Englische Commit-Messages (Conventional Commits: feat/fix/docs/chore)
- Ruff für Linting (`ruff check backend/`)
- Migrations immer committen
- Echte Unicode-Zeichen: ä, ö, ü, ß — nicht ae, oe, ue, ss


## Barrierefreiheit

Bei **jeder** Template-Änderung WCAG 2.1 AA einhalten. Verbindliche Regeln: **`docs/ACCESSIBILITY.md`**
