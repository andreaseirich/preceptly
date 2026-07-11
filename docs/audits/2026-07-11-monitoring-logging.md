# Audit-Bericht: Monitoring / Logging Bestandsaufnahme

**Datum:** 2026-07-11
**Autor:** Sonnet (Audit-Agent)
**Status:** Fixes ausstehend — Entscheidung: Option B (mail_admins + SMTP)

## 1. Error-Tracking (Sentry o.ae.)
Nicht vorhanden. Kein sentry-sdk in requirements.txt, kein sentry_sdk.init(), keine DSN-Konfiguration, keine Sentry-Middleware.

## 2. Django LOGGING-Konfiguration
settings.py:326-372 definiert zwei Handler: console (stdout, alle Logger) und file (logs/tutorflow.log, nur apps.ai, apps.lessons.email_service, apps.lessons.views_booking). Der root-Logger und django-Logger haben ausschliesslich den console-Handler. Alle unbehandelten Exceptions (500er) landen nur auf Railway-stdout. Kein mail_admins-Handler, kein ADMINS-Setting, kein SMTP. Sobald die Railway-Log-Retention ablaeuft, sind diese Fehler faktisch verloren.

## 3. Health-Check
/health/ existiert - apps/core/urls.py:34 -> apps/core/views_health.py:8-10, gibt {"status": "ok"} zurueck. Korrekt aus Middleware-Auth ausgenommen (middleware.py:33).

## 4. Kritische Business-Events (Logging-Status)
- Stripe Webhook-Signatur ungueltig: kein logger-Call, nur HTTP 400 (views_stripe.py:465)
- Stripe allgemeine Webhook-Exception: logger.exception() vorhanden (views_stripe.py:494)
- Stripe Security-Mismatches (customer/subscription): logger.error() vorhanden (views_stripe.py:569, 616, 695)
- invoice.payment_failed (Zahlungsausfall): KEIN logger-Call, laeuft still (views_stripe.py:682-714)
- subscription.deleted (Kuendigung/Ablauf): KEIN logger-Call, laeuft still (views_stripe.py:669-679)
- eRecht24-API-Fehler: logger.warning() vorhanden (erecht24_service.py:54, 170, 183, 205)
- Billing-Duplikate/Fehler: logger.error() vorhanden (billing/services.py:177, 217)

Kernproblem: Auch wo logger.error() korrekt gesetzt ist, landen alle Logs nur auf Railway-stdout - ohne persistente Weiterleitung gibt es keine aktive Benachrichtigung.

## 5. Empfehlung des Audits und Entscheidung
Drei Optionen genannt:
- A) Sentry Free-Tier (empfohlen fuer vollstaendiges Error-Tracking)
- B) Django mail_admins + SMTP (E-Mail bei 500ern, kein externer Dienst noetig)
- C) Railway-Logs reichen erstmal (Luecke bleiben stille Stripe-Events)

**ENTSCHEIDUNG (2026-07-11, Andreas Eirich): Option B - mail_admins wird umgesetzt.**
