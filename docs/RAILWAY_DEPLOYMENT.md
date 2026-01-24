# Railway Deployment – TutorFlow

## Übersicht

Diese Anleitung erklärt, wie du TutorFlow auf Railway.app deployst. Railway ist die empfohlene Plattform für Django-Anwendungen, da sie einfach zu verwenden ist und automatische Deployments von GitHub unterstützt.

## Warum Railway?

**Vorteile:**
- Sehr einfach zu verwenden
- Guter Django-Support
- Automatische Deployments von GitHub
- PostgreSQL-Datenbank inklusive
- Kostenloser Tier verfügbar
- Automatische SSL-Zertifikate

## Schnellstart mit Railway

### 1. Railway Account erstellen

1. Gehe zu https://railway.app
2. Melde dich mit GitHub an
3. Erlaube Railway den Zugriff auf deine Repositories

### 2. Neues Projekt erstellen

1. Klicke auf "New Project"
2. Wähle "Deploy from GitHub repo"
3. Wähle dein `tutorflow` Repository
4. Railway erkennt automatisch, dass es sich um ein Django-Projekt handelt

### 3. PostgreSQL-Datenbank hinzufügen

1. Klicke auf "New" → "Database" → "PostgreSQL"
2. Railway erstellt automatisch eine PostgreSQL-Datenbank
3. Die Datenbank-URL wird automatisch als Umgebungsvariable gesetzt

### 4. Umgebungsvariablen konfigurieren

Gehe zum "Variables" Tab und füge folgende Variablen hinzu:

```bash
SECRET_KEY=<generiere-einen-starken-key>
DEBUG=False
ALLOWED_HOSTS=*.railway.app
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

**Wichtig:**
- `SECRET_KEY`: Generiere einen starken Secret Key (z.B. mit `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DATABASE_URL`: Railway setzt diese Variable automatisch, wenn du `${{Postgres.DATABASE_URL}}` verwendest
- `ALLOWED_HOSTS`: Erlaubt alle Railway-Subdomains. Für eine Custom Domain füge diese auch hinzu: `*.railway.app,deine-domain.com`

### 5. Build-Einstellungen (optional)

Railway erkennt Django automatisch und verwendet die `railway.json` Konfiguration. Falls du manuelle Einstellungen benötigst:

- **Build Command**: `cd backend && pip install -r ../requirements.txt && python manage.py collectstatic --noinput`
- **Start Command**: `cd backend && python manage.py migrate && gunicorn tutorflow.wsgi:application --bind 0.0.0.0:$PORT`

### 6. Deploy

1. Railway deployt automatisch bei jedem Git-Push zu `main`
2. Du erhältst eine URL wie `https://tutorflow-production.up.railway.app`
3. Die Anwendung ist sofort verfügbar!

## Erste Schritte nach dem Deploy

### Demo-Daten laden (optional)

Falls du die Demo-Daten verwenden möchtest:

1. Öffne die Railway Console
2. Führe folgenden Befehl aus:
   ```bash
   cd backend && python manage.py loaddata fixtures/demo_data.json
   ```

**Demo-Logins:**
- Premium User: `demo_premium` / `demo123`
- Standard User: `demo_user` / `demo123`

### Übersetzungen kompilieren

```bash
cd backend && python manage.py compilemessages
```

## Custom Domain einrichten

1. Gehe zu deinem Projekt in Railway
2. Klicke auf "Settings" → "Domains"
3. Füge deine Domain hinzu
4. Folge den DNS-Anweisungen
5. Aktualisiere `ALLOWED_HOSTS` mit deiner Domain

## Umgebungsvariablen für LLM (optional)

Falls du die Premium-Features (AI Lesson Plans) verwenden möchtest:

```bash
LLM_API_KEY=dein-api-key
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-3.5-turbo
MOCK_LLM=0
```

Für Demos ohne echte API-Calls:
```bash
MOCK_LLM=1
```

## Monitoring und Logs

- **Logs**: Klicke auf "Deployments" → Wähle einen Deployment → "View Logs"
- **Metrics**: Railway zeigt automatisch CPU, Memory und Network-Usage
- **Health Check**: Die Anwendung hat einen `/health/` Endpoint

## Updates

Railway deployt automatisch bei jedem Push zu `main`. Du kannst auch manuell deployen:

1. Gehe zu "Deployments"
2. Klicke auf "Redeploy" für den letzten Deployment

## Backup-Strategie

Railway bietet automatische Backups für PostgreSQL-Datenbanken:

1. Gehe zu deiner Datenbank
2. Klicke auf "Backups"
3. Konfiguriere automatische Backups

## Troubleshooting

### Statische Dateien werden nicht angezeigt

Stelle sicher, dass `collectstatic` im Build-Prozess ausgeführt wird:
```bash
cd backend && python manage.py collectstatic --noinput
```

### Datenbank-Migrationen schlagen fehl

Führe Migrationen manuell aus:
```bash
cd backend && python manage.py migrate
```

### 500 Errors

Prüfe die Logs in Railway:
1. Gehe zu "Deployments"
2. Wähle den fehlgeschlagenen Deployment
3. Klicke auf "View Logs"

### Umgebungsvariablen werden nicht erkannt

Stelle sicher, dass alle Variablen im "Variables" Tab gesetzt sind und dass `${{Postgres.DATABASE_URL}}` für die Datenbank verwendet wird.

## Kosten

Railway bietet:
- **Free Tier**: $5 Credits pro Monat (ausreichend für kleine Projekte)
- **Pro Plan**: Ab $20/Monat für größere Projekte

## Weitere Ressourcen

- [Railway Dokumentation](https://docs.railway.app)
- [Django auf Railway](https://docs.railway.app/guides/django)
- [PostgreSQL auf Railway](https://docs.railway.app/databases/postgresql)

## Hilfe

Falls du Probleme hast:
1. Prüfe die Railway Logs
2. Erstelle ein Issue im Repository
3. Kontaktiere den Railway Support
