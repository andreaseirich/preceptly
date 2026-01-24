# Netlify Deployment – TutorFlow

## ⚠️ Wichtiger Hinweis

**Netlify ist nicht ideal für Django-Anwendungen!**

Netlify ist hauptsächlich für statische Websites und JAMstack-Anwendungen (z.B. React, Vue, Next.js) optimiert. Django ist eine Full-Stack-Framework, das einen Server (WSGI/ASGI) benötigt, um zu laufen.

## Warum Netlify nicht ideal ist

1. **Keine Server-Unterstützung**: Netlify hostet keine persistenten Server-Prozesse
2. **Serverless-Funktionen**: Netlify Functions sind für kleine, isolierte Funktionen gedacht, nicht für vollständige Django-Anwendungen
3. **Datenbank**: Netlify bietet keine integrierte Datenbank-Unterstützung
4. **Statische Dateien**: Netlify ist für statische Sites optimiert, Django rendert Seiten dynamisch

## Empfohlene Alternativen

### 1. Railway.app (Empfohlen) ⭐

**Vorteile:**
- Sehr einfach zu verwenden
- Guter Django-Support
- Automatische Deployments von GitHub
- PostgreSQL-Datenbank inklusive
- Kostenloser Tier verfügbar

**Schritte:**
1. Gehe zu https://railway.app
2. Erstelle ein neues Projekt
3. Verbinde dein GitHub-Repository
4. Railway erkennt automatisch Django
5. Setze Umgebungsvariablen in Railway Dashboard:
   ```
   SECRET_KEY=dein-secret-key
   DEBUG=False
   ALLOWED_HOSTS=deine-domain.railway.app
   DATABASE_URL=postgresql://... (wird automatisch gesetzt)
   ```
6. Railway deployt automatisch bei jedem Git-Push

### 2. Render.com

**Vorteile:**
- Kostenloser Tier verfügbar
- Guter Django-Support
- Automatische SSL
- PostgreSQL-Datenbank verfügbar

**Schritte:**
1. Gehe zu https://render.com
2. Erstelle einen neuen "Web Service"
3. Verbinde dein GitHub-Repository
4. Wähle "Django" als Environment
5. Setze Build Command: `cd backend && pip install -r ../requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput`
6. Setze Start Command: `cd backend && gunicorn tutorflow.wsgi:application`
7. Füge PostgreSQL-Datenbank hinzu
8. Setze Umgebungsvariablen

### 3. Fly.io

**Vorteile:**
- Sehr gut für Django
- Globale Edge-Netzwerk
- Docker-basiert

**Schritte:**
1. Installiere Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Erstelle `fly.toml`:
   ```bash
   fly launch
   ```
3. Fly.io erstellt automatisch die Konfiguration
4. Deploy: `fly deploy`

### 4. DigitalOcean App Platform

**Vorteile:**
- Professionelle Plattform
- Gute Dokumentation
- PostgreSQL verfügbar

## Falls du trotzdem Netlify verwenden möchtest

**Option 1: Frontend/Backend trennen**
- Frontend (React/Vue) auf Netlify hosten
- Backend (Django) auf Railway/Render/Fly.io hosten
- Frontend kommuniziert mit Backend über API

**Option 2: Django als Serverless (nicht empfohlen)**
- Sehr kompliziert
- Erfordert erhebliche Umstrukturierung
- Nicht für Produktion empfohlen

## Schnellstart mit Railway (Empfohlen)

1. **Railway Account erstellen:**
   - Gehe zu https://railway.app
   - Melde dich mit GitHub an

2. **Neues Projekt erstellen:**
   - Klicke auf "New Project"
   - Wähle "Deploy from GitHub repo"
   - Wähle dein `tutorflow` Repository

3. **Datenbank hinzufügen:**
   - Klicke auf "New" → "Database" → "PostgreSQL"
   - Railway erstellt automatisch eine PostgreSQL-Datenbank

4. **Umgebungsvariablen setzen:**
   - Gehe zu "Variables" Tab
   - Füge folgende Variablen hinzu:
     ```
     SECRET_KEY=<generiere-einen-starken-key>
     DEBUG=False
     ALLOWED_HOSTS=*.railway.app,deine-domain.com
     DATABASE_URL=${{Postgres.DATABASE_URL}}
     ```
   - Railway setzt `DATABASE_URL` automatisch, wenn du die Datenbank-Variable verwendest

5. **Build-Einstellungen:**
   - Railway erkennt automatisch Django
   - Falls nicht, setze:
     - **Build Command**: `cd backend && pip install -r ../requirements.txt && python manage.py collectstatic --noinput`
     - **Start Command**: `cd backend && python manage.py migrate && gunicorn tutorflow.wsgi:application --bind 0.0.0.0:$PORT`

6. **Deploy:**
   - Railway deployt automatisch bei jedem Git-Push
   - Du erhältst eine URL wie `https://tutorflow-production.up.railway.app`

## Vergleich der Plattformen

| Plattform | Kostenloser Tier | Django-Support | Einfachheit | Empfehlung |
|-----------|------------------|----------------|-------------|------------|
| Railway   | ✅ Ja            | ⭐⭐⭐⭐⭐      | ⭐⭐⭐⭐⭐    | ⭐⭐⭐⭐⭐ |
| Render    | ✅ Ja            | ⭐⭐⭐⭐        | ⭐⭐⭐⭐      | ⭐⭐⭐⭐   |
| Fly.io    | ✅ Ja            | ⭐⭐⭐⭐        | ⭐⭐⭐       | ⭐⭐⭐⭐   |
| Netlify   | ✅ Ja            | ❌ Nein        | ❌          | ❌         |

## Nächste Schritte

1. **Wähle eine Plattform** (empfohlen: Railway)
2. **Folge der Anleitung** für die gewählte Plattform
3. **Teste deine Deployment** mit den Demo-Daten
4. **Richte eine Custom Domain ein** (optional)

## Hilfe

Falls du Hilfe bei der Deployment auf einer der Plattformen benötigst, erstelle ein Issue im Repository oder kontaktiere den Maintainer.
