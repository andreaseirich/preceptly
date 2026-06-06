# Railway Umgebungsvariablen — Preceptly

Alle Secrets werden als Railway Environment Variables gesetzt, nie im Code.

## E-Mail (iCloud SMTP)

| Variable | Wert |
|----------|------|
| `EMAIL_HOST` | `smtp.mail.me.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_USE_TLS` | `True` |
| `EMAIL_USE_SSL` | `False` |
| `EMAIL_HOST_USER` | `andreaseirich2004@icloud.com` |
| `EMAIL_HOST_PASSWORD` | *(App-spezifisches Passwort — in Railway setzen)* |
| `DEFAULT_FROM_EMAIL` | `andreaseirich2004@icloud.com` |
| `SITE_URL` | `https://preceptly.up.railway.app` |

**Hinweis:** Für iCloud muss ein App-spezifisches Passwort generiert werden unter:
appleid.apple.com → Anmeldung und Sicherheit → App-spezifische Passwörter

## Weitere Pflicht-Variablen

| Variable | Beschreibung |
|----------|-------------|
| `SECRET_KEY` | Django Secret Key |
| `DATABASE_URL` | PostgreSQL-URL (von Railway automatisch gesetzt) |
| `ALLOWED_HOSTS` | `preceptly.up.railway.app` |
| `DEBUG` | `False` |

## Stripe (Subscription)

| Variable | Beschreibung |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe API Secret Key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe Publishable Key |
| `STRIPE_WEBHOOK_SECRET` | Stripe Webhook Secret |

## eRecht24

| Variable | Beschreibung |
|----------|-------------|
| `ERECHT24_API_KEY` | API-Schlüssel von eRecht24 |
| `ERECHT24_PLUGIN_KEY` | Plugin-Schlüssel |
| `ERECHT24_PUSH_SECRET` | Webhook-Secret |
| `ERECHT24_CLIENT_ID` | Client-ID nach Registrierung |
