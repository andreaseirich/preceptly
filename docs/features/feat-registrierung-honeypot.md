# Registrierung: Honeypot gegen Automaten

**Stand:** 26.10.2026 · Auftrag von Andreas: „Sichere die Registrierung mit einem Honeypot ab.“

## Anlass

Am 25.10.2026 meldete die App eine Registrierung mit Zufallsnamen und der Adresse eines Formular-Test-Dienstes
(`formtests.info`): sehr wahrscheinlich ein Automat. Die Registrierung hatte bis dahin nur die Drosselung (5 Versuche je
10 Minuten und IP, `throttle_register`), kein CAPTCHA, keinen Honeypot und keine Sperre für Wegwerf-Domains. Jede
angelegte Registrierung löst außerdem eine Bestätigungsmail an die angegebene (fremde) Adresse aus.

## Verhalten

Das Registrierformular hat ein zusätzliches Textfeld `homepage`:

- **Für Menschen unsichtbar und nicht erreichbar:** aus dem Bild geschoben (kein `display:none`, das erkennen Automaten
  leichter), `aria-hidden="true"` auf dem Umschlag, `tabindex="-1"`, `autocomplete="off"`. Screenreader und Tastatur
  überspringen es. Ohne CSS steht dort „Bitte lass dieses Feld leer.“
- **Automaten füllen es aus.** Ist das Feld nicht leer (auch nur ein Leerzeichen), wird **kein Konto angelegt, keine
  Mail verschickt**, und es erscheint die allgemeine Meldung „Registrierung fehlgeschlagen. Bitte versuche es erneut.“
  Ein Mensch, bei dem ein Browser das Feld doch gefüllt hätte, kann also einfach noch einmal absenden (das Feld ist
  danach wieder leer).
- Im Log steht eine Warnung („Registration rejected: honeypot field was filled“), ohne Benutzernamen und Adresse.
- Die Drosselung bleibt unverändert und zählt auch abgelehnte Versuche mit.

Der Feldname ist absichtlich keiner, den Browser oder Passwortmanager von selbst ausfüllen (kein `name`, `email`, `phone`,
`address`, `organization`).

## Grenzen

Ein Honeypot hält einfache Automaten ab, die jedes Textfeld ausfüllen. Gezielte Angreifer, die nur die sichtbaren Felder
bedienen, hält er nicht auf. Falls es weiterhin Zufallskonten gibt, wäre der nächste Schritt Cloudflare Turnstile oder
eine Sperre für Wegwerf-Domains. Bewusst nicht gebaut: eine Zeitfalle („zu schnell abgeschickt“), weil Passwortmanager
das Formular in unter einer Sekunde ausfüllen und echte Nutzer treffen würden.

## Code

| Teil | Ort |
|---|---|
| Feld und Prüfung (`RegisterForm.clean`, `HONEYPOT_FIELD`) | `apps/core/forms.py` |
| Unsichtbares Feld | `apps/core/templates/core/register.html` |
| Tests | `apps/core/tests/test_register_honeypot.py` |
