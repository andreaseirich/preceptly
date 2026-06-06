# Preceptly – Eltern/Schüler-Portal: Implementierungsplan

## Architektur-Entscheidung

**Separate Portal-Accounts** (nicht Rollen im Tutor-User):
- Tutor: bestehender `User` (Django auth) — unverändert
- Eltern/Schüler: neues `PortalUser`-Modell, eigene Login-Seite `/portal/login/`
- Eltern sehen nur ihre Kinder; Schüler sehen nur ihre eigenen Daten
- Tutor verwaltet alles wie bisher

## Neue Django-App: `apps.portal`

### Modelle

```
PortalUser
  - user: OneToOne → django.contrib.auth.User
  - role: "parent" | "student"
  - tutor: FK → auth.User (welchem Lehrer gehört dieses Konto)
  - created_at

StudentPortalLink
  - portal_user: FK → PortalUser (role=student)
  - student: OneToOne → students.Student
  - invite_token: CharField (für Einladungs-E-Mail, UUID)
  - is_active: BooleanField

ParentStudentLink
  - parent: FK → PortalUser (role=parent)
  - student: FK → students.Student
  (M2M: mehrere Eltern pro Kind, mehrere Kinder pro Eltern)

PortalMessage
  - sender_portal_user: FK → PortalUser (null=True, Schüler/Eltern schreiben)
  - sender_is_tutor: BooleanField (True wenn Tutor schreibt)
  - student: FK → students.Student
  - text: TextField
  - created_at: DateTimeField
  - read_by_tutor: BooleanField
  - read_by_portal: BooleanField
```

### Erweiterungen bestehender Modelle

**lessons.Session** (neue Felder):
- `homework`: TextField (blank, null) — Hausaufgaben für nächste Stunde
- `meeting_url`: CharField (max 500, blank, null) — Zoom/Meet-Link

**students.Student** (neue App: `apps.portal` ProgressNote):
```
ProgressNote
  - student: FK → students.Student
  - tutor: FK → auth.User
  - date: DateField (auto_now_add)
  - text: TextField
  - created_at: DateTimeField
```

## URL-Struktur

```
/portal/                    → Weiterleitung je nach Rolle (StudentHome / ParentHome)
/portal/login/              → Portal-Login (separates Template)
/portal/logout/             → Portal-Logout
/portal/student/            → Schüler-Startseite (kommende Stunden, Hausaufgaben)
/portal/student/lessons/    → Stundenhistorie des Schülers
/portal/parent/             → Eltern-Startseite (Übersicht alle Kinder)
/portal/parent/<pk>/        → Detail-Ansicht eines Kindes
/portal/messages/           → Nachrichten (Tutor ↔ Eltern/Schüler)
/portal/messages/<student_pk>/ → Nachrichtenthread für Schüler
```

## Views

- `PortalLoginView` — Form-Login, Session setzt `portal_user_id`
- `PortalLogoutView` — löscht Portal-Session
- `PortalDispatchView` — `/portal/` → Redirect je nach Rolle
- `StudentHomeView` — kommende Stunden, letzte Hausaufgaben
- `StudentLessonListView` — Stundenhistorie
- `ParentHomeView` — alle verknüpften Kinder + Zusammenfassung
- `ParentStudentDetailView` — Stunden + Notizen eines Kindes
- `PortalMessageView` — Nachrichten lesen + schreiben (simpel, kein WebSocket)

## Tutor-seitige Verwaltung (in bestehenden Apps)

- Student-Detailseite: Einladungs-Link generieren (für Schüler/Eltern)
- Student-Detailseite: ProgressNotes anlegen/anzeigen
- Stundenformular: homework + meeting_url Felder
- Stundendetail: Hausaufgaben anzeigen, Nachrichtenlink

## Templates

Eigener Base-Template: `portal/base.html` (minimales Layout, kein Tutor-Menü)
- `portal/login.html`
- `portal/student_home.html`
- `portal/student_lessons.html`
- `portal/parent_home.html`
- `portal/parent_student_detail.html`
- `portal/messages.html`

## Sicherheit

- Jede Portal-View prüft: `portal_user_id` in Session + `portal_user.tutor == lesson.contract.student.user`
- Kein Kreuz-Zugriff zwischen verschiedenen Tutoren
- Einladungs-Token: einmalig verwendbar (nach Aktivierung nullen)

## Implementierungs-Phasen

### Phase 1 — Portal-App + Modelle (2–3 Tage)
1. `apps/portal/__init__.py`, `models.py`, `views.py`, `urls.py`
2. Migrationen für Session (homework, meeting_url) + ProgressNote
3. settings.py: `apps.portal` zu INSTALLED_APPS
4. urls.py: `portal/` einbinden
5. Ruff + Tests + Commit

### Phase 2 — Tutor-seitige UI (1–2 Tage)
1. Student-Detailseite: Einladungslinks, ProgressNotes
2. Stundenformular: homework + meeting_url
3. Stundendetail: Hausaufgaben anzeigen

### Phase 3 — Portal-Templates (2 Tage)
1. Schüler-Portal (Startseite, Stundenhistorie)
2. Eltern-Portal (Kinder-Übersicht, Detail)
3. Nachrichten

### Phase 4 — Nachrichten + Feinschliff (1 Tag)
1. PortalMessage-Views + Templates
2. Ungelesene-Badge im Tutor-Menü
3. Deployment-Test

## Implementierungs-Status

| Phase | Status | Commits |
|-------|--------|---------|
| Phase 1 — Portal-App + Modelle | ✅ DONE | d1da54e, 021135b |
| Phase 2 — Tutor-seitige UI | 🔄 IN PROGRESS | — |
| Phase 3 — Portal-Templates | ⏳ PENDING | — |
| Phase 4 — Nachrichten + Feinschliff | ⏳ PENDING | — |
