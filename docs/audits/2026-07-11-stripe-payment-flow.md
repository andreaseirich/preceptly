# Audit-Bericht: Stripe-Zahlungsfluss Preceptly (End-to-End)

**Datum:** 2026-07-11
**Autor:** Fable (Security-Audit-Agent)
**Status:** Fixes erledigt (2026-07-11)

**Scope:** backend/apps/core/views_stripe.py, stripe_utils.py, models.py, feature_flags.py, settings.py, sowie alle Erstellungspfade fuer Studenten/Rechnungen. Nur Analyse, keine Code-Aenderungen.

## 1. Checkout-Session-Erstellung - sicher
Die Preis-ID kommt ausschliesslich serverseitig aus den Settings. Der Client sendet nur einen Tier-Namen (starter/pro/business), der ueber eine feste Map aufgeloest wird (views_stripe.py:135-144 bzw. :318-327). Ein unbekannter Tier-Wert faellt auf den Pro-Preis zurueck. Betrag/Preis sind nicht manipulierbar. metadata.user_id wird serverseitig aus request.user gesetzt - ebenfalls nicht manipulierbar.

## 2. Success-Redirect - sicher
?checkout=success steuert nur ein Erfolgs-Banner (views.py:360-362, show_stripe_success_banner). Der Abo-Status (subscription_tier) wird ausschliesslich in Webhook-Handlern geschrieben - die einzigen Schreibstellen im gesamten Code sind views_stripe.py:522 und :526 (_set_premium). Ein manipulierter Redirect schaltet nichts frei.

## 3. Subscription-Lifecycle - weitgehend korrekt, zwei Anmerkungen
Behandelt werden checkout.session.completed, customer.subscription.created/updated, customer.subscription.deleted, invoice.payment_failed, invoice.paid (views_stripe.py:532-549). Aktivierung/Tier-Wechsel laufen ueber den Preis-zu-Tier-Mapping in subscription.updated (:630-666), Kuendigung setzt sauber auf free (:669-679), Dunning: past_due/unpaid gelten sofort als nicht-premium (stripe_utils.py:22-27) - streng, aber konsistent.

Anmerkung A (Medium-Low): _handle_invoice_payment_failed liest invoice.get("subscription") (views_stripe.py:684). In neueren Stripe-API-Versionen (ab "Basil" 2025) liegt das Feld unter parent.subscription_details.subscription - je nach gepinnter API-Version des Webhook-Endpoints ist dieser Handler ein stiller No-op. Abgefedert wird das dadurch, dass Stripe bei Zahlungsausfall auch subscription.updated (Status past_due) sendet, was korrekt behandelt wird. Trotzdem pruefen, welche API-Version der Endpoint nutzt.

Anmerkung B (Medium-Low, Tier-Kurzschluss): _handle_checkout_session_completed ruft _set_premium ohne price_id auf (:597); bei einem neuen Kunden ist profile.stripe_price_id noch leer und _price_id_to_tier(None) defaultet auf "pro" (:515). Ein Starter-Kaeufer bekommt also kurzzeitig Pro, bis subscription.created/updated den Tier korrigiert. Normalerweise Sekunden - aber kombiniert mit Fund 4 (unten) kann die Korrektur dauerhaft ausbleiben.

## 4. Idempotenz - wichtigster Fund (Medium-High)
Fehlgeschlagene Events werden nie erneut verarbeitet. Der Ablauf in stripe_webhook_view (views_stripe.py:478-503):
1. Event-Zeile wird per get_or_create VOR der Verarbeitung angelegt (:480).
2. Wirft _handle_stripe_event eine Exception, wird 500 zurueckgegeben, damit Stripe retryt (:501) - aber die Event-Zeile bleibt bestehen.
3. Beim Stripe-Retry greift "if not created: return 200" (:484-485) -> das Event wird als "schon verarbeitet" verworfen, obwohl es nie erfolgreich verarbeitet wurde.

Das StripeWebhookEvent-Modell (models.py:189-196) hat kein processed-Flag, und die Zeile wird bei Fehler nicht geloescht - der Kommentar "es sei denn, der Event wurde bereits erfolgreich verarbeitet" (:477) beschreibt eine Logik, die nicht existiert. Konsequenz: Ein transienter DB-Fehler bei subscription.deleted -> Nutzer behaelt Premium dauerhaft (Umsatzverlust); bei checkout.session.completed/subscription.created -> zahlender Kunde bekommt kein Premium (Support-Fall). Zusaetzlich: in _handle_invoice_payment_failed fuehrt ein Stripe-API-Fehler beim Subscription.retrieve zu stillem return mit 200 (:707-709) - auch hier kein Retry, obwohl nichts verarbeitet wurde.

Empfehlung: processed_at-Feld ergaenzen; Zeile erst nach erfolgreicher Verarbeitung als abgeschlossen markieren (bzw. bei Fehler loeschen), damit der 500-Retry-Pfad tatsaechlich wirkt. Doppelte Provisionierung/Rechnungen entstehen dagegen NICHT - die Dedup-Logik gegen doppelte Zustellung funktioniert, und alle Handler sind ohnehin idempotent formuliert (Status-Sync statt inkrementeller Aktionen).

## 5. Race Conditions - Doppel-Abo moeglich (Medium)
- Doppelklick/gleiche Minute: abgefangen durch idempotency_key=f"checkout:{user.id}:{int(time.time()//60)}" (:205, :379) - gleicher Key -> gleiche Session. Gut. (Randfall: anderer Tier innerhalb derselben Minute -> Stripe-Idempotency-Konflikt -> sauber abgefangene Fehlermeldung.)
- Kein serverseitiger Schutz gegen Zweit-Abo: Weder SubscriptionCheckoutView noch StripeCheckoutView pruefen, ob der Nutzer bereits ein aktives Abo hat. Das Template blendet den Button fuer Premium-Nutzer nur aus (settings.html:351-356). Per direktem POST oder zwei Tabs (Checkout in Tab A abschliessen, in Tab B den vorher geladenen Checkout ebenfalls abschliessen) entstehen zwei aktive Stripe-Subscriptions = Doppelabbuchung. Der Ownership-Check gegen abweichende subscription_id (:615-622) greift hier nicht, weil die Profil-Aufloesung ueber metadata.user_id laeuft und diesen Branch umgeht - die zweite Subscription ueberschreibt stripe_subscription_id; kuendigt der Nutzer dann die getrackte, verliert er Premium, waehrend die erste weiter abbucht. Kein Privilege-Escalation-Risiko, aber Kundenschaden/Support-Risiko. Empfehlung: Vor Session-Erstellung pruefen, ob subscription_tier != free bzw. eine aktive stripe_subscription_id existiert -> stattdessen ins Billing-Portal leiten.
- Customer-Anlage ist korrekt gegen Races geschuetzt (select_for_update + idempotency_key=customer:{user.id}, :152-171).

## 6. Fehlerbehandlung - gut
Alle Stripe-Aufrufe in den Views fangen stripe.error.StripeError (deckt auch Timeouts/APIConnectionError ab) und liefern eine uebersetzte Meldung - Redirect mit messages.error fuer HTML, 502-JSON fuer AJAX (_stripe_checkout_error_response, :107-113). Kein Stacktrace-Leak. Redirects zu Stripe werden auf https://*.stripe.com validiert (:75-90). Kleiner Architekturpunkt: stripe.Customer.create laeuft INNERHALB von transaction.atomic() mit gehaltener Row-Lock (:152-179) - bei langsamer Stripe-API werden DB-Verbindung und Lock bis zu Timeout-Dauer gehalten (bei checkout.session.completed wurde dasselbe Muster bereits bewusst behoben, Kommentar "H11" :561).

## 7. Free-Tier-Limits - Soft-Limits mit inkonsistentem Pfad (Medium-Low)
Wichtig zur Einordnung: Die Limits sind bewusst als Soft-Limits gebaut - es wird gewarnt, aber trotzdem gespeichert ("Your student was saved", "Your invoice was created"):
- Studenten: students/views.py:55-70 (StudentCreateView.post) - Warnung ab dem 6. Studenten, Speichern erfolgt trotzdem.
- Rechnungen: billing/views.py:242-277 (form_valid) - Warnung ab der 9. Rechnung im Monat, Erstellung erfolgt trotzdem. Rechnungen entstehen nur ueber InvoiceService.create_invoice_from_lessons, dessen einziger produktiver Aufrufer diese View ist - kein Umgehungspfad.
- Umgehungspfad beim Studenten-Limit: Da "Student = Contract" ist, erzeugt ContractCreateView (contracts/views.py:113, form_valid ab :143) denselben Datensatz OHNE jede Limit-Pruefung oder Warnung (nur Demo-Limit). Ein Free-Nutzer, der ueber /contracts/create/ statt ueber die Studenten-Ansicht anlegt, sieht das Soft-Limit nie. Solange die Limits soft sind, ist das nur inkonsistente UX - sollten sie je hart werden, muss dieser Pfad zwingend mitgezogen werden.

## Zusatzfund: tote Preis-Whitelist (Medium)
STRIPE_PREMIUM_PRICE_IDS existiert nicht in settings.py (verifiziert per Suche ueber das gesamte Backend). Damit ist die als "[MEDIUM] Price-ID gegen Whitelist pruefen" kommentierte Pruefung in _handle_subscription_created_or_updated (views_stripe.py:642-652) ein No-op (allowed_prices immer leer -> Bedingung nie wahr), und _ALLOWED_PREMIUM_PRICES (:46) ist ungenutzter toter Code. Kombiniert mit dem "pro"-Default in _price_id_to_tier (:515) gilt: jede aktive Subscription mit beliebiger Preis-ID auf diesem Stripe-Account ergibt Tier "pro". Aktuell nicht ausnutzbar (Preise stammen aus dem eigenen Account), aber sobald jemals ein guenstigeres/fremdes Produkt ueber denselben Account laeuft, waere das eine Tier-Eskalation. Empfehlung: Setting definieren (alle 5 Preis-IDs) und den "pro"-Default auf "unbekannt -> free + Alarm-Log" aendern.

## Zusammenfassung
Kritische Funde: keine. Preisbildung, Webhook-als-Source-of-truth, Signatur/Replay-Schutz, Cross-Validierung von Customer-IDs und Fehlerbehandlung sind solide umgesetzt.

Mittlere Funde:
1. Webhook-Retry wirkungslos - Event wird vor Verarbeitung als verarbeitet markiert; nach Handler-Exception verwirft der Stripe-Retry das Event (views_stripe.py:480-501). Fail-open bei Kuendigungen, fail-closed bei Provisionierung.
2. Preis-Whitelist tot - STRIPE_PREMIUM_PRICE_IDS nicht definiert; unbekannte Preise defaulten auf "pro" (:642, :515).
3. Doppel-Abo moeglich - kein serverseitiger Guard gegen Checkout bei bereits aktivem Abo -> Doppelabbuchung bei Mehrtab-Nutzung (:117-216, :300-390).
4. invoice.payment_failed API-versionsabhaengig - invoice.subscription existiert in neueren Stripe-API-Versionen nicht mehr top-level (:684); gepinnte Endpoint-API-Version pruefen.

Best-Practice-Empfehlungen: processed_at-Flag fuer StripeWebhookEvent; Starter-Checkout setzt kurzzeitig "pro" bis subscription.updated eintrifft (:597 + :515); Stripe-API-Call aus der select_for_update-Transaktion bei der Customer-Anlage herausziehen (:152-179); Contract-Create-Pfad in die Free-Limit-Warnung einbeziehen (contracts/views.py:143); doppelte Checkout/Portal-View-Paare (StripeCheckoutView/SubscriptionCheckoutView) konsolidieren, um Drift zu vermeiden; doppelte @csrf_exempt/@require_POST-Dekoratoren am Webhook entfernen (:440-443, kosmetisch).

---

## Fix-Status (2026-07-11)

| Fund | Beschreibung | Status | Commit |
|------|-------------|--------|--------|
| Fund 4 (Medium-High) | Webhook-Retry wirkungslos — Event vor Verarbeitung als verarbeitet markiert; `processed_at`-Feld + Retry-Logik-Fix; `logger.warning` fuer `subscription.deleted` und `invoice.payment_failed` ergaenzt | Behoben | 43cd022 |
| Zusatzfund (Medium) | Preis-Whitelist tot — `STRIPE_PREMIUM_PRICE_IDS` nicht definiert; Default-"pro" auf fail-closed (free + Alarm) umgestellt; Setting scharf geschaltet | Behoben | a6ade0e |
| Fund 5 (Medium) | Doppel-Abo moeglich — serverseitiger Guard vor Checkout-Session-Erstellung eingefuegt | Behoben | 0f563b2 |
| Anmerkung A (Medium-Low) | `invoice.payment_failed` API-versionsabhaengig — Handler liest jetzt robust ueber beide Stripe-API-Versionen (legacy `subscription` und `parent.subscription_details.subscription`) | Behoben | 864fa9c |
