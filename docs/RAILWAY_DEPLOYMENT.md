# Railway Deployment – TutorFlow

## Overview

This guide explains how to deploy TutorFlow on Railway.app. Railway is the recommended platform for Django applications as it's easy to use and supports automatic deployments from GitHub.

## Why Railway?

**Advantages:**
- Very easy to use
- Great Django support
- Automatic deployments from GitHub
- PostgreSQL database included
- Free tier available
- Automatic SSL certificates

## Quick Start with Railway

### 1. Create Railway Account

1. Go to https://railway.app
2. Sign in with GitHub
3. Allow Railway access to your repositories

### 2. Create New Project

1. Click on "New Project"
2. Select "Deploy from GitHub repo"
3. Choose your `tutorflow` repository
4. Railway automatically detects that it's a Django project

### 3. Add PostgreSQL Database

1. Click on "New" → "Database" → "PostgreSQL"
2. Railway automatically creates a PostgreSQL database
3. The database URL is automatically set as an environment variable

### 4. Configure Environment Variables

Go to the "Variables" tab and add the following variables:

```bash
SECRET_KEY=<generate-a-strong-key>
DEBUG=False
ALLOWED_HOSTS=*.railway.app
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

**Important:**
- `SECRET_KEY`: Generate a strong secret key (e.g., using `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DATABASE_URL`: Railway sets this variable automatically when you use `${{Postgres.DATABASE_URL}}`
- `ALLOWED_HOSTS`: Allows all Railway subdomains. For a custom domain, also add it: `*.railway.app,your-domain.com`

### 5. Build Settings (optional)

Railway automatically detects Django and uses the `railway.json` configuration. If you need manual settings:

- **Build Command**: `cd backend && pip install -r ../requirements.txt && python manage.py collectstatic --noinput`
- **Start Command**: `cd backend && python manage.py migrate && gunicorn tutorflow.wsgi:application --bind 0.0.0.0:$PORT`

### 6. Deploy

1. Railway automatically deploys on every Git push to `main`
2. You'll receive a URL like `https://tutorflow-production.up.railway.app`
3. The application is immediately available!

## First Steps After Deploy

### Load Demo Data (optional)

If you want to use the demo data:

1. Open the Railway Console
2. Run the following command:
   ```bash
   cd backend && python manage.py loaddata fixtures/demo_data.json
   ```

**Demo Logins:**
- Premium User: `demo_premium` / `demo123`
- Standard User: `demo_user` / `demo123`

### Compile Translations

```bash
cd backend && python manage.py compilemessages
```

## Set Up Custom Domain

1. Go to your project in Railway
2. Click on "Settings" → "Domains"
3. Add your domain
4. Follow the DNS instructions
5. Update `ALLOWED_HOSTS` with your domain

## Environment Variables for LLM (optional)

If you want to use the Premium features (AI Lesson Plans):

```bash
LLM_API_KEY=your-api-key
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-3.5-turbo
MOCK_LLM=0
```

For demos without real API calls:
```bash
MOCK_LLM=1
```

## Monitoring and Logs

- **Logs**: Click on "Deployments" → Select a deployment → "View Logs"
- **Metrics**: Railway automatically displays CPU, Memory, and Network usage
- **Health Check**: The application has a `/health/` endpoint

## Updates

Railway automatically deploys on every push to `main`. You can also deploy manually:

1. Go to "Deployments"
2. Click on "Redeploy" for the last deployment

## Backup Strategy

Railway offers automatic backups for PostgreSQL databases:

1. Go to your database
2. Click on "Backups"
3. Configure automatic backups

## Troubleshooting

### Static Files Not Displaying

Make sure `collectstatic` is executed in the build process:
```bash
cd backend && python manage.py collectstatic --noinput
```

### Database Migrations Failing

Run migrations manually:
```bash
cd backend && python manage.py migrate
```

### 500 Errors

Check the logs in Railway:
1. Go to "Deployments"
2. Select the failed deployment
3. Click on "View Logs"

### Environment Variables Not Recognized

Make sure all variables are set in the "Variables" tab and that `${{Postgres.DATABASE_URL}}` is used for the database.

## Pricing

Railway offers:
- **Free Tier**: $5 credits per month (sufficient for small projects)
- **Pro Plan**: Starting at $20/month for larger projects

## Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [Django on Railway](https://docs.railway.app/guides/django)
- [PostgreSQL on Railway](https://docs.railway.app/databases/postgresql)

## Help

If you encounter problems:
1. Check the Railway logs
2. Create an issue in the repository
3. Contact Railway support
