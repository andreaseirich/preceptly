# Sicherheits- und Infrastrukturplan – tutorflow

**Erstellt:** Juni 2026  
**Autor:** Andreas Eirich  
**Basiert auf:** GERMADE Sicherheits- und Infrastrukturplan

---

## 1. Projektkontext

[Kurzbeschreibung des Projekts und seiner Sicherheitsanforderungen]

Server-Struktur:
```
Mac (Entwicklung)
    ↓ SSH
AI-Server (Hetzner, Ubuntu)
    ↓ SSH
tutorflow-server
    ↓
Siehe CLAUDE.md
```

---

## 2. Dokumentations- und Kontextstruktur (Fünf-Punkte-System)

Alle Projekte folgen dieser Struktur — kein Projekt ist ausgenommen:

1. **Projektstatus in Markdown** — Anforderungen, Feature-Tracking, Akzeptanzkriterien, Entscheidungen
2. **Kontext schichten** — CLAUDE.md (Tech-Stack), PRD.md (Vision/Zielgruppe), docs/features/ (Einzelfeatures), skills/
3. **Kontext isolieren** — Recherche+Planung in eigener Session, Implementierung separat
4. **Context Recovery** — Pro Skill eine Anleitung (siehe docs/CONTEXT_RECOVERY.md)
5. **Lesen, niemals raten** — Alle relevanten Dateien vor jeder Aktion laden

---

## 3. KI-Agenten-Workflow

**Aktueller Ansatz (ohne Fable 5):**
- Claude Sonnet (Gruppenleiter) koordiniert auf dem MacBook
- Agenten auf dem AI-Server: Haiku (Doku), Sonnet (Code), Opus (komplex), Fable (Security, derzeit gesperrt)
- Agenten lesen immer — sie raten niemals
- Alle Änderungen werden in GitHub committet (rückverfolgbar)
- Bei kritischen Aktionen: menschliche Überprüfung bevorzugt

---

## 4. Sicherheitsarchitektur

### 4.1 Aktiver Schutz
- [ ] Fail2ban aktiv
- [ ] UFW Firewall aktiv (nur notwendige Ports)
- [ ] SSH-Zugang nur vom AI-Server autorisiert

### 4.2 Geplanter Schutz
- [ ] SSH-Port auf Nicht-Standard (1024–65535)
- [ ] SSH-Key-Rotation alle 90 Tage
- [ ] IP-Whitelist: SSH nur vom AI-Server
- [ ] Agenten-Rechte eingrenzen (kein Root auf Systemdateien)

---

## 5. Automatisches Sicherheitsmonitoring

Alle Projekte auf dem AI-Server werden durch das zentrale Security-Monitoring überwacht:

**Stufe 0** — Normal → nur Log  
**Stufe 1** — Verdächtig → Pushover-Alarm (hoch)  
**Stufe 2** — Kritisch → Pushover-Alarm (kritisch, Stummmodus-Bypass) + automatischer AI-Server-Shutdown

Überwachte Parameter:
- authorized_keys Veränderungen
- Aktive SSH-Sessions
- Fehlgeschlagene Login-Versuche
- Offene Ports (Vergleich mit Baseline)
- CPU-Last (Schwellwert: Kerne × Faktor)
- Integrität kritischer Systemdateien (Hash)

---

## 6. Offene Punkte

| Priorität | Aufgabe | Status |
|-----------|---------|--------|
| Hoch | SSH-Port auf Nicht-Standard | ⏳ Offen |
| Hoch | Pushover + automatischer Shutdown | ⏳ Offen |
| Hoch | Regelmäßige Sicherheitsprüfung | ⏳ Offen |
| Mittel | IP-Whitelist SSH | ⏳ Offen |
| Mittel | SSH-Key-Rotation | ⏳ Offen |
| Mittel | Agenten-Rechte eingrenzen | ⏳ Offen |

---

## 7. Grundsatz

Sicherheit ist kein Zustand, sondern ein Prozess. Ziel: Angriffe frühzeitig erkennen, Schaden begrenzen, schnell reagieren.
