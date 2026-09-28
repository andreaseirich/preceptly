# Rechnungen: Sperre, Storno und Nummern

**Stand:** 28.09.2026 · Anlass: Prüfbericht vom 27.09.2026 (F1, F2), entschieden von Andreas am 27./28.09.2026

## Warum

Bis 27.09.2026 ließ sich eine Rechnung auch nach dem Versand noch ändern,
löschen und ihre PDF neu erzeugen. Die Fassung, die der Kunde bekommen hatte,
war danach nicht mehr feststellbar (§ 146 Abs. 4 AO, GoBD). Im Free-Tarif trug
die PDF außerdem die plattformweite Datenbank-ID als Nummer. Die zählte über
alle Tutoren hinweg und verriet damit, wie viele Rechnungen es auf der ganzen
Plattform gibt.

## Verhalten

| Status | Empfänger ändern | Löschen | PDF neu erzeugen | Zahlungsstatus | Stornieren |
|---|---|---|---|---|---|
| Entwurf | ja | ja | ja | ja | nein |
| Versendet | nein | nein | nur falls noch keine existiert | ja | ja |
| Bezahlt | nein | nein | nur falls noch keine existiert | ja | ja, mit Hinweis auf die Rückzahlung |
| Storniert | nein | nein | nein | nein | nein |

- **Beim Versenden** wird die PDF festgeschrieben, falls es noch keine gibt.
- **Die Stornorechnung** bekommt eine eigene fortlaufende Nummer und negative
  Beträge. Ihre PDF heißt „Stornorechnung“, verweist auf das Original und
  fordert keine Zahlung.
- **Original und Stornorechnung** stehen danach beide auf „storniert“. Sie
  zählen weder als Umsatz noch als offener Posten. Die Detailseiten verweisen
  gegenseitig aufeinander.
- **Die Stunden** des Originals gelten wieder als unterrichtet und lassen sich
  neu abrechnen. Die Posten der Stornorechnung verweisen deshalb auf keine
  Stunde, nur im Text.
- **Das Storno** gibt es in allen Tarifen, denn ausgestellte Rechnungen lassen
  sich nicht mehr löschen.

## Rechnungsnummern

Jeder Tutor zählt ab `INV-0001` hoch, seit 28.09.2026 in allen Tarifen.
Stornorechnungen laufen in derselben Folge mit. Alte Free-Rechnungen behalten
ihre ID als Nummer (`Invoice.display_number`), denn ausgestellte Rechnungen
werden nicht umnummeriert. Der Starter-Tarif bietet seitdem statt der Nummern
den Statusfilter der Rechnungsliste.

## Code

| Teil | Ort |
|---|---|
| Sperre | `Invoice.is_locked`, Prüfungen in `billing/views.py` |
| Storno | `InvoiceService.cancel_invoice`, View `invoice_cancel` |
| Nummern | `InvoiceService.next_invoice_number` |
| Abrechenbare Stunden | `InvoiceService.get_billable_lessons`: keine Stunde aus einer nicht stornierten Rechnung |
| PDF | `pdf_service.py`: Titel, Verweis, kein Zahlungsblock |
| Tests | `test_invoice_lock.py`, `test_invoice_cancel.py` |

## Offen

Die rechtliche Einordnung soll ein Steuerberater bestätigen, sobald Andreas
einen beauftragt.
