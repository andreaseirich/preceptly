# Portal: Absagen, Verschieben und Serienende nachvollziehbar

**Stand:** 02.10.2026 · Entschieden von Andreas am 02.10.2026: Benachrichtigung
einbauen, abgesagte Termine aufbewahren.

## Warum

Bis 02.10.2026 löschte eine Absage im Portal die Stunde spurlos. Der Tutor
erfuhr weder von einer Absage noch von einer Verschiebung. Wer wann abgesagt
hatte, ließ sich nicht mehr feststellen.

## Verhalten

- **Absage im Portal:** Die Stunde verschwindet wie bisher aus dem Kalender,
  die Zeit ist wieder frei und lässt sich neu buchen. Vorher wird sie ins
  Archiv geschrieben: Termin, wer gebucht hatte, wer wann abgesagt hat.
- **Serie beenden:** Jede kommende Stunde der Serie landet einzeln im Archiv.
- **Verschieben:** Die Stunde bleibt eine Stunde und wird nicht archiviert.
- **Benachrichtigung:** Bei Absage, Verschiebung und Serienende bekommt der
  Tutor eine E-Mail und eine Push-Nachricht. Abschaltbar in den Einstellungen
  unter „Benachrichtigungen“, getrennt von den Buchungen
  (`notify_portal_change_email`, `notify_portal_change_push`).
- **Anzeige beim Tutor:** auf der Seite des Schülers unter „Im Portal
  abgesagte Termine“, die letzten 20, mit Konto und E-Mail.
- **Anzeige im Portal:** unter „Stunden“ bei „Abgesagte Termine“, ohne
  E-Mail-Adressen.

## Entscheidung: Archiv statt Status „abgesagt“

Die Stunde bleibt nicht als `Session` mit Status `cancelled` stehen. 29
Abfragen im Code filtern nicht nach Status, darunter Konflikterkennung,
Finanzkennzahlen, iCloud-Sync, Kalender-Abo und Portal-Kalender. Eine
abgesagte Stunde würde dort weiter wie ein Termin behandelt, zum Beispiel als
Konflikt mit der Stunde, die eine andere Familie in die freie Zeit bucht.
Das Archiv (`CancelledSession`) berührt keine dieser Abfragen.

Nicht archiviert werden Stunden, die der Tutor selbst löscht.

## Code

| Teil | Ort |
|---|---|
| Archiv | `apps/lessons/cancelled_models.py`, `cancellation_service.py`, Migration `lessons/0020_portal_cancellations` |
| Anzeige | `apps/lessons/booking_origin.py` (`cancellation_info`, `cancelled_overview`) |
| Texte der Benachrichtigung | `apps/portal/change_notices.py` |
| Versand | `email_service.send_change_notification_portal`, Vorlagen `portal/email/change_notification.*` |
| Portal-Ansichten | `PortalSessionCancelView`, `PortalSessionRescheduleView`, `PortalRecurringCancelView` |
| Einstellung | `NotificationPreference.notify_portal_change_*`, Migration `core/0034_portal_cancellations` |
| Tests | `apps/portal/test_cancel_archive.py` |
