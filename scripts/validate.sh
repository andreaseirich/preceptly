#!/bin/bash
# Validierungsskript für TutorFlow
# Führt verschiedene Checks und Tests durch

set -e  # Stoppe bei Fehlern

echo "🔍 TutorFlow Validierung"
echo "========================"
echo ""

# Farben für Output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Prüfe ob wir im richtigen Verzeichnis sind
if [ ! -f "backend/manage.py" ]; then
    echo -e "${RED}❌ Fehler: backend/manage.py nicht gefunden. Bitte im Projekt-Root ausführen.${NC}"
    exit 1
fi

cd backend

# Aktiviere venv falls vorhanden
if [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

echo -e "${YELLOW}1. Django System Check...${NC}"
python manage.py check
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Django Check erfolgreich${NC}"
else
    echo -e "${RED}❌ Django Check fehlgeschlagen${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}2. Tests ausführen...${NC}"
python manage.py test --verbosity=0
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Alle Tests erfolgreich${NC}"
else
    echo -e "${RED}❌ Tests fehlgeschlagen${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}3. Prüfe auf TODO-Kommentare in produktivem Code...${NC}"
TODO_COUNT=$(grep -r "TODO\|FIXME" --include="*.py" apps/ tutorflow/ 2>/dev/null | grep -v "test" | grep -v "__pycache__" | wc -l)
if [ "$TODO_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Gefunden: $TODO_COUNT TODO/FIXME-Kommentare${NC}"
    grep -r "TODO\|FIXME" --include="*.py" apps/ tutorflow/ 2>/dev/null | grep -v "test" | grep -v "__pycache__" || true
else
    echo -e "${GREEN}✅ Keine TODO-Kommentare gefunden${NC}"
fi
echo ""

echo -e "${YELLOW}4. Prüfe auf Debug-Ausgaben (print, pdb)...${NC}"
DEBUG_COUNT=$(grep -r "print(" --include="*.py" apps/ tutorflow/ 2>/dev/null | grep -v "test" | grep -v "__pycache__" | wc -l)
PDB_COUNT=$(grep -r "pdb\|breakpoint" --include="*.py" apps/ tutorflow/ 2>/dev/null | grep -v "test" | grep -v "__pycache__" | wc -l)
if [ "$DEBUG_COUNT" -gt 0 ] || [ "$PDB_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Gefunden: $DEBUG_COUNT print()-Aufrufe, $PDB_COUNT pdb/breakpoint${NC}"
    grep -r "print(" --include="*.py" apps/ tutorflow/ 2>/dev/null | grep -v "test" | grep -v "__pycache__" || true
    grep -r "pdb\|breakpoint" --include="*.py" apps/ tutorflow/ 2>/dev/null | grep -v "test" | grep -v "__pycache__" || true
else
    echo -e "${GREEN}✅ Keine Debug-Ausgaben gefunden${NC}"
fi
echo ""

echo -e "${YELLOW}5. Prüfe Dokumentation...${NC}"
REQUIRED_DOCS=("README.md" "CHANGELOG.md" "docs/ARCHITECTURE.md" "docs/ETHICS.md" "docs/PHASES.md" "docs/CHECKPOINTS.md" "docs/DEVPOST.md")
MISSING_DOCS=()
for doc in "${REQUIRED_DOCS[@]}"; do
    if [ ! -f "../$doc" ]; then
        MISSING_DOCS+=("$doc")
    fi
done
if [ ${#MISSING_DOCS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ Alle Dokumentationsdateien vorhanden${NC}"
else
    echo -e "${RED}❌ Fehlende Dokumentation: ${MISSING_DOCS[*]}${NC}"
    exit 1
fi
echo ""

echo -e "${GREEN}✅ Validierung erfolgreich abgeschlossen!${NC}"
echo ""

