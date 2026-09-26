# Konto-E-Mail und „Passwort vergessen" (Tutoren)

**Stand:** 26.09.2026 · entschieden von Andreas am 26.09.2026

## Warum

Bis 26.09.2026 war die E-Mail-Adresse bei der Registrierung freiwillig; 2 von
3 echten Tutor-Konten hatten keine. Ohne Adresse

- ließ sich ein vergessenes Passwort nicht zurücksetzen — für Tutoren gab es
  gar keinen Reset,
- ist der Tutor als Verantwortlicher nicht erreichbar, etwa bei einer
  Datenpanne (Art. 33 Abs. 2 DSGVO),
- fehlen Rechnungen, Erinnerungen und Buchungsbenachrichtigungen still.

## Verhalten

| Teil | Verhalten | Code |
|---|---|---|
| Registrierung | E-Mail ist Pflichtfeld | `RegisterForm` |
| Konten ohne E-Mail | nach dem Login zuerst `/account/email/`; Hinweisleiste auf jeder Seite, bis die Adresse da ist | `views_account_email.py`, `TutorFlowLoginView.get_success_url`, Context-Processor `account_email_context` |
| Passwort vergessen | `/password-reset/`: Link per Mail, 1 Stunde gültig, einmal nutzbar; die Mail nennt auch den Benutzernamen | `views_password.py`, `PASSWORD_RESET_TIMEOUT` |
| Adresse bestätigen | jede neue Adresse bekommt einen Link (7 Tage gültig): bei der Registrierung, beim Nachtragen, beim Ändern über den Änderungslink. Bis dahin Hinweisleiste mit „Bestätigungslink senden“ (höchstens 3 pro Stunde) und „Falsche Adresse?“ | `send_verification`, `EmailVerifyView`, `UserProfile.email_verified_at` |
| E-Mail ändern | Einstellungen → E-Mail: neue Adresse + aktuelles Passwort → Bestätigungslink an die neue Adresse (24 Stunden); danach Hinweis an die alte | `views_account_email.py`, `SettingsView._change_email` |
| Stripe | die bei Stripe hinterlegte Adresse wird **nie** geändert, nur eine fehlende ergänzt | `_maybe_update_stripe_customer_email` |

Ausgenommen sind die Demo-Konten (`demo_user`, `demo_premium`) und
Portal-Konten — Schüler und Eltern haben ihren eigenen Reset im Portal.

## Schutz

- Reset und Registrierung verraten nicht, ob es ein Konto gibt: gleiche
  Antwort, die Mail geht im Hintergrund raus.
- Reset höchstens 5 Anfragen pro Minute und IP, Ändern höchstens 5 pro Stunde
  und Konto.
- Ändern nur mit dem aktuellen Passwort. Der Link gilt nur für das Konto, das
  ihn angefordert hat, und nur solange die alte Adresse noch gilt.
- Mit dem neuen Passwort meldet Django alle anderen Sitzungen ab.
- Der Reset im Portal (Schüler, Eltern) hat seit 26.09.2026 dieselbe Frist von
  einer Stunde; vorher galt sein Link 7 Tage.

## Bewusst nicht gemacht

- Eine unbestätigte Adresse sperrt nichts: Das Konto bleibt nutzbar, und
  „Passwort vergessen“ geht auch an sie. Die Bestätigung soll Tippfehler
  sichtbar machen, nicht aussperren.
- Die Adresse bei Stripe ändern (Entscheidung Andreas, 26.09.2026).
