# Deployment Guide – TutorFlow

## Overview

This guide provides instructions for deploying TutorFlow in a production environment.

## Prerequisites

- Python 3.12 or higher
- PostgreSQL (recommended) or another production-grade database
- Web server (nginx, Apache) for reverse proxy
- WSGI server (Gunicorn, uWSGI) for Django application
- SSL certificate for HTTPS

## Database Setup

TutorFlow uses an environment-first database configuration:

- **Production/CI**: Set `DATABASE_URL` (e.g. `postgresql://user:pass@host:5432/tutorflow`). The settings use `dj-database-url` to parse this value.
- **Local/Demo fallback**: If `DATABASE_URL` is not set, SQLite is used at `backend/db.sqlite3`.

### PostgreSQL (recommended for production)

1. **Install PostgreSQL:**
   ```bash
   sudo apt-get install postgresql postgresql-contrib  # Ubuntu/Debian
   # or
   brew install postgresql  # macOS
   ```

2. **Create database and user:**
   ```sql
   CREATE DATABASE tutorflow;
   CREATE USER tutorflow_user WITH PASSWORD 'your-password';
   GRANT ALL PRIVILEGES ON DATABASE tutorflow TO tutorflow_user;
   ```

3. **Configure environment:**
   ```bash
   export DATABASE_URL="postgresql://tutorflow_user:your-password@localhost:5432/tutorflow"
   ```

## Environment Variables

Create a `.env` file (or set environment variables) with:

```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://tutorflow_user:password@localhost/tutorflow

# LLM API (for premium features)
LLM_API_KEY=your-api-key
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-3.5-turbo
```

**Important:** Never commit `.env` files to the repository. Add `.env` to `.gitignore`.

## Production Settings

TutorFlow uses **env-first configuration**. The main `settings.py` reads from environment variables. Ensure these are set:

- `SECRET_KEY` – Required in production
- `DEBUG=False` – Never use True in production
- `ALLOWED_HOSTS` – Comma-separated list of allowed hosts
- `DATABASE_URL` – PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/dbname`). Uses `dj-database-url`; if unset, falls back to SQLite.

For static/media paths and logging, override `STATIC_ROOT`, `MEDIA_ROOT`, and `LOGGING` via environment or a local settings override if needed.

## Deployment Steps

1. **Clone repository:**
   ```bash
   git clone <repository-url>
   cd tutorflow
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install gunicorn  # For WSGI server
   ```

4. **Run migrations:**
   ```bash
   cd backend
   python manage.py migrate
   ```

5. **Compile translations:**
   ```bash
   python manage.py compilemessages
   ```

6. **Collect static files:**
   ```bash
   python manage.py collectstatic --noinput
   ```

## WSGI Server (Gunicorn)

**Run Gunicorn:**
```bash
cd backend
gunicorn tutorflow.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

**Systemd service** (`/etc/systemd/system/tutorflow.service`):
```ini
[Unit]
Description=TutorFlow Gunicorn daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/tutorflow/backend
ExecStart=/path/to/tutorflow/venv/bin/gunicorn tutorflow.wsgi:application --bind 127.0.0.1:8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl enable tutorflow
sudo systemctl start tutorflow
```

## Reverse Proxy (nginx)

**Example nginx configuration** (`/etc/nginx/sites-available/tutorflow`):
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/key.pem;

    location /static/ {
        alias /var/www/tutorflow/static/;
    }

    location /media/ {
        alias /var/www/tutorflow/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/tutorflow /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Backup Strategy

**Database backup:**
```bash
# PostgreSQL
pg_dump -U tutorflow_user tutorflow > backup_$(date +%Y%m%d).sql

# Restore
psql -U tutorflow_user tutorflow < backup_20231205.sql
```

**Automated backups:**
- Set up cron job for daily database backups
- Store backups in secure, off-site location
- Test restore procedure regularly

## Monitoring

- **Logs**: Monitor Django logs (`/var/log/tutorflow/django.log`)
- **System resources**: Monitor CPU, memory, disk usage
- **Error tracking**: Consider integrating Sentry or similar service
- **Uptime monitoring**: Use services like UptimeRobot or Pingdom

## Security Checklist

- [ ] `DEBUG = False` in production
- [ ] `SECRET_KEY` stored in environment variable
- [ ] HTTPS enabled (SSL certificate configured)
- [ ] `ALLOWED_HOSTS` configured correctly
- [ ] Database credentials stored securely
- [ ] Static files served by web server (not Django)
- [ ] Regular security updates for dependencies
- [ ] Firewall configured (only necessary ports open)
- [ ] Regular backups configured and tested

## Deployment with Docker

Docker provides the easiest way to deploy TutorFlow in production.

### Prerequisites

- Docker and Docker Compose installed
- Domain name (optional, for SSL)

### Quick Start

1. **Clone repository:**
   ```bash
   git clone <repository-url>
   cd tutorflow
   ```

2. **Create `.env` file:**
   ```bash
   SECRET_KEY=your-secret-key-here
   DEBUG=False
   ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
   DATABASE_URL=postgresql://tutorflow_user:tutorflow_password@db:5432/tutorflow
   LLM_API_KEY=your-api-key  # Optional, for premium features
   ```

3. **Build and start services:**
   ```bash
   docker-compose up -d --build
   ```

4. **Run migrations:**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py compilemessages
   docker-compose exec web python manage.py collectstatic --noinput
   ```

5. **Access application:**
   - Application: `http://localhost:8000`

### Docker Services

- **web**: Django application (Gunicorn)
- **db**: PostgreSQL database
- **nginx**: Reverse proxy and static file server

### Updating

```bash
git pull
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
docker-compose restart web
```

### Backup Database

```bash
docker-compose exec db pg_dump -U tutorflow_user tutorflow > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
docker-compose exec -T db psql -U tutorflow_user tutorflow < backup_20231205.sql
```

### SSL/HTTPS with Let's Encrypt

For production with SSL, use a reverse proxy (e.g., Traefik) or configure nginx with Let's Encrypt certificates.

## Troubleshooting

**Common issues:**
- **Static files not loading**: Run `collectstatic` and check nginx configuration
- **Database connection errors**: Verify database credentials and network connectivity
- **Permission errors**: Check file permissions for static/media directories
- **500 errors**: Check Django logs for detailed error messages
- **Docker issues**: Check logs with `docker-compose logs web`

## Updates

When updating TutorFlow:

1. Pull latest changes: `git pull`
2. Activate virtual environment: `source venv/bin/activate`
3. Install/update dependencies: `pip install -r requirements.txt`
4. Run migrations: `python manage.py migrate`
5. Compile translations: `python manage.py compilemessages`
6. Collect static files: `python manage.py collectstatic --noinput`
7. Restart Gunicorn: `sudo systemctl restart tutorflow`

**Or with Docker:**
```bash
git pull
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
docker-compose restart web
```

