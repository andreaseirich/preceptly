# Context Recovery

## Schnellstart für neue Sessions

### Vor jeder Änderung
1. `CLAUDE.md` lesen — Tech-Stack und Regeln
2. `PRD.md` lesen — aktueller Feature-Status
3. Betroffene Datei lesen, bevor etwas geändert wird
4. Niemals raten — immer Dateien/Logs prüfen

### Sessions trennen
- **Recherche & Planung:** Erst Docs lesen, Anforderungen klären
- **Implementierung:** Separate Session nach klarem Plan

### Bei unbekanntem Zustand
- `git log --oneline -10` — letzte Commits prüfen
- `git status` — uncommitted changes prüfen
- Relevante Docs aus `docs/` lesen
