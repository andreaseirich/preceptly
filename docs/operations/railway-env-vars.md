# Railway Umgebungsvariablen — Preceptly

Alle Secrets werden als Railway Environment Variables gesetzt, nie im Code.

**Stand:** 22.09.2026 — vollständig gegen `backend/tutorflow/settings.py` und die Stellen in `backend/apps/` abgeglichen.

Spalte **Fehlt sie?** sagt, was passiert, wenn die Variable nicht gesetzt ist. Die meisten Funktionen schalten sich dann still ab, das fällt im Betrieb erst auf, wenn jemand sie vermisst.

## Basis (Pflicht)

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `SECRET_KEY` | Django Secret Key | **App startet nicht** |
| `ALLOWED_HOSTS` | `preceptly.de,www.preceptly.de` | **App startet nicht** (außer `DEBUG=True`) |
| `DATABASE_URL` | PostgreSQL-URL | Fällt auf lokale SQLite-Datei zurück — in Produktion Datenverlust |
| `DEBUG` | `False` in Produktion | Default `False` |
| `SITE_URL` | `https://preceptly.de`, für Links in E-Mails | Default `https://preceptly.de` |
| `CSRF_TRUSTED_ORIGINS` | zusätzliche Origins für CSRF | Default leer |
| `TRUSTED_PROXIES` | Proxy-Bereiche für die Ermittlung der echten Client-IP | Default `100.64.0.0/10` (Railway). Falsch gesetzt ⇒ alle Rate-Limits zählen pro Proxy statt pro Besucher |

## Infrastruktur

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `REDIS_URL` | Redis für Cache und WebSocket-Channel-Layer | Fällt auf prozesslokalen Speicher zurück: **Rate-Limits und Login-Sperren gelten nur je Prozess**, Meetings funktionieren nicht über mehrere Instanzen |
| `CALDAV_ENCRYPTION_KEY` | Fernet-Schlüssel für die iCloud-Zugangsdaten der Tutoren | Kalender-Sync bricht mit „gerade nicht verfügbar" ab, es wird nichts unverschlüsselt gespeichert |

## Sicherheit / HTTPS

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `SECURE_SSL_REDIRECT` | HTTP → HTTPS erzwingen | `True` (außer `DEBUG`/Tests) |
| `SESSION_COOKIE_SECURE` | Session-Cookie nur über HTTPS | `True` (außer `DEBUG`) |
| `CSRF_COOKIE_SECURE` | CSRF-Cookie nur über HTTPS | `True` (außer `DEBUG`) |
| `SECURE_HSTS_SECONDS` | HSTS-Dauer | `31536000` |
| `SECURE_HSTS_PRELOAD` | HSTS-Preload-Flag | `False` |

## E-Mail (iCloud SMTP)

| Variable | Wert / Beschreibung | Fehlt sie? |
|----------|---------------------|------------|
| `EMAIL_HOST` | `smtp.mail.me.com` | Default gesetzt |
| `EMAIL_PORT` | `587` | Default gesetzt |
| `EMAIL_USE_TLS` | `True` | Default gesetzt |
| `EMAIL_USE_SSL` | `False` | Default gesetzt |
| `EMAIL_HOST_USER` | Apple-ID | **Kein Mailversand** |
| `EMAIL_HOST_PASSWORD` | App-spezifisches Passwort | **Kein Mailversand** |
| `DEFAULT_FROM_EMAIL` | Absender | Default `andreaseirich2004@icloud.com` |
| `INVOICE_FROM_EMAIL` | Absender für Rechnungen | Default `noreply@preceptly.de` |
| `SERVER_EMAIL` | Absender für Fehler-Mails | Default = `DEFAULT_FROM_EMAIL` |
| `EMAIL_TIMEOUT` | SMTP-Timeout in Sekunden | Default `10` |
| `EMAIL_BACKEND` | abweichendes Backend (z. B. Konsole) | Default SMTP mit Timeout-Wrapper |
| `NOTIFICATION_EMAIL` | Empfänger für Buchungsbenachrichtigungen | Benachrichtigung wird übersprungen, nur Log-Warnung |
| `ADMIN_NOTIFICATION_EMAIL` | Empfänger für Admin-Meldungen | Default `info@preceptly.de` |

App-spezifisches Passwort erstellen: appleid.apple.com → Anmeldung und Sicherheit → App-spezifische Passwörter.

## Stripe (Abonnements)

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `STRIPE_SECRET_KEY` | API Secret Key | Checkout antwortet mit 503 |
| `STRIPE_WEBHOOK_SECRET` | Webhook-Signatur | Webhook lehnt alles ab ⇒ **Abos werden nie aktiviert** |
| `STRIPE_PRICE_ID_STARTER` | Preis-ID Tarif Starter | Tarif wird im Checkout nicht angeboten |
| `STRIPE_PRICE_ID_PRO` | Preis-ID Tarif Pro | Tarif wird im Checkout nicht angeboten |
| `STRIPE_PRICE_ID_BUSINESS` | Preis-ID Tarif Business | Tarif wird im Checkout nicht angeboten |
| `STRIPE_PRICE_ID_MONTHLY` | Alt-ID, Fallback für „Pro" | — |
| `STRIPE_PRICE_ID_YEARLY` | Alt-ID (Jahresabo) | — |
| `STRIPE_CHECKOUT_SUCCESS_URL` | Rücksprung nach erfolgreichem Checkout | Default: Einstellungsseite |
| `STRIPE_CHECKOUT_CANCEL_URL` | Rücksprung nach Abbruch | Default: Einstellungsseite |
| `STRIPE_PORTAL_RETURN_URL` | Rücksprung aus dem Stripe-Portal | Default: Einstellungsseite |

Achtung: Eine Preis-ID, die hier **nicht** hinterlegt ist, ordnet der Webhook keinem Tarif zu und stuft das Abo bewusst als „free" ein (mit ALERT im Log).

## KI-Unterrichtspläne

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `LLM_API_BASE_URL` | Endpunkt des Sprachmodells (aktuell selbst gehostetes Ollama über Tailscale) | Default `https://api.anthropic.com` |
| `LLM_API_KEY` | API-Schlüssel | Ohne Schlüssel läuft der Mock-Modus statt echter Generierung |
| `LLM_MODEL_NAME` | Modellname | Default `claude-haiku-4-5-20251001` |
| `LLM_TIMEOUT_SECONDS` | Timeout je Anfrage | Default `30` |
| `TAILSCALE_OLLAMA_HOST` | Host im Tailnet, für den HTTP über den lokalen Proxy erlaubt ist | Ohne diesen Eintrag wird eine `http://`-Adresse abgelehnt |
| `MOCK_LLM` | `1` erzwingt Beispielantworten (Tests/Demo) | Default aus |

## Push-Benachrichtigungen (Web Push)

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `VAPID_PUBLIC_KEY` | öffentlicher VAPID-Schlüssel | **Push still deaktiviert**, Schaltfläche ohne Wirkung |
| `VAPID_PRIVATE_KEY` | privater VAPID-Schlüssel | **Push still deaktiviert** |
| `VAPID_ADMIN_EMAIL` | Kontaktadresse für den Push-Dienst | Push-Dienste können Zustellung ablehnen |

## Video-Meetings (TURN)

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `TURN_URL` | TURN-Server | Default `turn:46.224.151.16:3478` |
| `TURN_USER` | Benutzername | Default `preceptly` |
| `TURN_CREDENTIAL` | Passwort | **Meetings hinter NAT/Firewall kommen nicht zustande** — im Heimnetz oft unauffällig, im Mobilfunk nicht |

## eRecht24 (Rechtstexte und Widerrufs-Button)

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `ERECHT24_API_KEY` | API-Schlüssel | Impressum und Datenschutzerklärung fallen auf den statischen Kurztext zurück |
| `ERECHT24_PLUGIN_KEY` | Plugin-Schlüssel | wie oben |
| `ERECHT24_PUSH_SECRET` | Secret für den Aktualisierungs-Webhook | Aktualisierungen werden abgelehnt |
| `ERECHT24_CLIENT_ID` | Client-ID nach Registrierung | — |
| `ERECHT24_REVOCATION_WEBHOOK_SECRET` | HMAC-Secret des Widerrufs-Webhooks | Webhook antwortet mit 503 ⇒ **Widerrufe über den Button kommen nicht an** |

## Betrieb und Monitoring

| Variable | Beschreibung | Fehlt sie? |
|----------|--------------|------------|
| `BARK_SERVER_URL` | Bark-Server für Fehler-Pushes | Keine Push-Alarme bei Fehlern |
| `BARK_DEVICE_KEY` | Geräteschlüssel | wie oben |
| `BARK_AUTH_USER` / `BARK_AUTH_PASSWORD` | Basic-Auth des Bark-Servers | nur nötig, wenn der Server sie verlangt |
| `DEV_STATS_PASSWORD` | Passwort für `/dev/stats/` | Seite bleibt gesperrt |
| `BACKUP_DIR` | Zielverzeichnis für `manage.py backup_db` | Default: Projektverzeichnis |
| `BACKUP_KEEP` | Anzahl aufzubewahrender Backups | Default `7` |

## Nicht mehr verwendet

`STRIPE_PUBLISHABLE_KEY` stand früher in dieser Liste, wird aber nirgends mehr gelesen — der Checkout läuft vollständig über Stripe Checkout Sessions.
