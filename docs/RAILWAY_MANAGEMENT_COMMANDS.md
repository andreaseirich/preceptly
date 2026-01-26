# Running Django Management Commands on Railway

## Problem

When running Django management commands locally with `railway run`, you may encounter:
```
could not translate host name "postgres.railway.internal" to address
```

This happens because `postgres.railway.internal` is an internal Railway hostname that only works within the Railway network, not from your local machine.

## Solutions

### Option 1: Railway Web Console (Recommended)

1. Go to https://railway.app
2. Open your project
3. Open your web service (e.g., "tutorflow")
4. Click on "Deployments" → Select latest deployment
5. Click "View Logs" or look for a "Shell" button
6. Run commands directly in the container:
   ```bash
   python manage.py load_demo_data
   python manage.py reset_demo_passwords
   ```

### Option 2: Use Public DATABASE_URL

Railway provides both internal and public database URLs. To run commands locally:

1. Get the public DATABASE_URL from Railway:
   - Go to Railway Dashboard → Your Project → PostgreSQL Service
   - Click on "Variables" tab
   - Look for `DATABASE_URL` or `PUBLIC_DATABASE_URL`
   - Copy the public URL (usually contains `*.up.railway.app` or a public IP)

2. Temporarily override DATABASE_URL:
   ```bash
   # Get the public URL from Railway dashboard, then:
   export DATABASE_URL="postgresql://user:password@public-hostname.up.railway.app:5432/railway"
   python manage.py load_demo_data
   python manage.py reset_demo_passwords
   ```

### Option 3: Railway CLI with Service Shell

```bash
# This should open a shell in the container (if supported)
railway shell --service tutorflow

# Then run commands:
python manage.py load_demo_data
python manage.py reset_demo_passwords
```

### Option 4: Add Command to Entrypoint (One-time Setup)

If you need to run commands automatically on deploy, you can modify `scripts/entrypoint.sh`:

```bash
# Add before gunicorn starts:
if [ "${LOAD_DEMO_DATA:-0}" = "1" ]; then
  python manage.py load_demo_data || echo "Warning: Failed to load demo data"
fi
```

Then set `LOAD_DEMO_DATA=1` in Railway Variables (remove after first successful load).

## Getting Public DATABASE_URL

1. Railway Dashboard → Your Project
2. Click on PostgreSQL service
3. Go to "Variables" tab
4. Look for `DATABASE_URL` - Railway may provide both internal and public URLs
5. If only internal URL is shown, check the "Connect" tab for connection strings

## Troubleshooting

- **"postgres.railway.internal" error**: You're running locally. Use Railway Web Console or get public DATABASE_URL.
- **"No supported database found"**: `railway connect` is for database connections, not web service commands.
- **Commands work in container but not locally**: This is expected - use Railway Web Console for management commands.
