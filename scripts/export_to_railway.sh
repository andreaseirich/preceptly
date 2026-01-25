#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Prüfe und aktiviere virtuelle Umgebung falls vorhanden
if [ -d "${ROOT_DIR}/venv" ]; then
    echo "🔧 Aktiviere virtuelle Umgebung: ${ROOT_DIR}/venv"
    source "${ROOT_DIR}/venv/bin/activate"
elif [ -d "${ROOT_DIR}/.venv" ]; then
    echo "🔧 Aktiviere virtuelle Umgebung: ${ROOT_DIR}/.venv"
    source "${ROOT_DIR}/.venv/bin/activate"
elif [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "✅ Virtuelle Umgebung bereits aktiviert: ${VIRTUAL_ENV}"
else
    echo "⚠️  Keine virtuelle Umgebung gefunden."
    echo "   Bitte aktiviere eine virtuelle Umgebung oder installiere Django global."
    echo "   Beispiel: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

cd "${ROOT_DIR}/backend"

# Prüfe, ob psycopg2 installiert ist (benötigt für PostgreSQL)
if ! python -c "import psycopg2" 2>/dev/null; then
    echo "⚠️  psycopg2-binary nicht gefunden. Installiere Abhängigkeiten..."
    pip install -q psycopg2-binary || {
        echo "❌ Fehler beim Installieren von psycopg2-binary"
        echo "   Bitte führe manuell aus: pip install psycopg2-binary"
        exit 1
    }
    echo "✅ psycopg2-binary installiert"
fi

# Lade lokale .env-Datei
if [ -f "${ROOT_DIR}/.env" ]; then
    # Sichere Methode zum Laden von .env (ohne Kommentare und leere Zeilen)
    # macOS-kompatible Methode
    set -a
    while IFS= read -r line || [ -n "$line" ]; do
        # Überspringe Kommentare und leere Zeilen
        case "$line" in
            \#*|'') continue ;;
            *) export "$line" ;;
        esac
    done < "${ROOT_DIR}/.env"
    set +a
    echo "✅ .env-Datei geladen"
fi

# Speichere Railway DATABASE_URL temporär (NACH dem Laden der .env)
RAILWAY_DB_URL="${DATABASE_URL:-}"

if [ -n "${RAILWAY_DB_URL}" ]; then
    echo "✅ Railway DATABASE_URL gefunden: ${RAILWAY_DB_URL:0:50}..."
else
    echo "⚠️  DATABASE_URL noch nicht gesetzt"
fi

# Exportiere von lokaler Datenbank (ohne DATABASE_URL, nutzt SQLite)
echo "📤 Exportiere Daten von lokaler Datenbank..."
export DATABASE_URL=""
DUMP_FILE="${ROOT_DIR}/db_export.json"

# Exportiere alle TutorFlow Apps mit natürlichen Keys für bessere Kompatibilität
# --natural-foreign: Verwendet natürliche Foreign Keys (z.B. username statt ID)
# --natural-primary: Verwendet natürliche Primary Keys wo möglich
# Wichtig: auth muss auch exportiert werden, damit User-Objekte vorhanden sind
python manage.py dumpdata \
    auth \
    contenttypes \
    core \
    students \
    contracts \
    lessons \
    blocked_times \
    lesson_plans \
    ai \
    billing \
    --natural-foreign \
    --natural-primary \
    --indent 2 \
    --output "${DUMP_FILE}"

echo "✅ Export abgeschlossen: ${DUMP_FILE}"

# Prüfe, ob Railway DATABASE_URL gesetzt ist
if [ -z "${RAILWAY_DB_URL:-}" ]; then
    echo "❌ Fehler: DATABASE_URL nicht in .env gefunden!"
    echo "Bitte stelle sicher, dass DATABASE_URL in .env gesetzt ist."
    echo ""
    echo "Aktueller Inhalt von .env:"
    if [ -f "${ROOT_DIR}/.env" ]; then
        grep "DATABASE_URL" "${ROOT_DIR}/.env" || echo "  (nicht gefunden)"
    else
        echo "  (.env-Datei existiert nicht)"
    fi
    exit 1
fi

echo "📥 Importiere Daten nach Railway..."
echo "DATABASE_URL: ${RAILWAY_DB_URL:0:30}..." # Nur ersten Teil anzeigen

# Setze Railway DATABASE_URL für Import
export DATABASE_URL="${RAILWAY_DB_URL}"

# Führe Migrationen aus, um Tabellen zu erstellen
echo "🔄 Führe Migrationen auf Railway aus..."
python manage.py migrate --noinput

# Lösche vorhandene Daten für sauberen Import
echo "🗑️  Lösche vorhandene Daten auf Railway..."
python manage.py flush --noinput || echo "⚠️  Flush fehlgeschlagen (möglicherweise keine Daten vorhanden)"

# Importiere nach Railway
# --ignorenonexistent: Ignoriert fehlende Objekte (falls einige bereits existieren)
echo "📥 Importiere Daten..."
python manage.py loaddata "${DUMP_FILE}" --ignorenonexistent

echo "✅ Daten erfolgreich nach Railway importiert!"
echo "🗑️  Lösche temporäre Export-Datei..."
rm -f "${DUMP_FILE}"
echo "✅ Fertig!"