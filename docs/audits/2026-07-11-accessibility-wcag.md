# Audit-Bericht: Barrierefreiheit WCAG 2.1 AA

**Datum:** 2026-07-11
**Autor:** Opus (Accessibility-Audit-Agent)
**Status:** Fixes ausstehend

Geprueft (rein lesend, keine Codeaenderungen):
- PWA-Install-Banner + Modal - backend/apps/core/templates/core/base.html
- Pricing-Sektion - backend/apps/core/templates/core/landing.html
- Invoice-Detailseite - backend/apps/billing/templates/billing/invoice_detail.html
- Meeting-Pre-Join-Lobby - backend/apps/meeting/templates/meeting/room.html

Gesamt-Bewertung: Kritisch (verhindert Nutzung mit AT vollstaendig): keine. Mittelschwer (WCAG-AA-Verstoss, Kernfunktion bleibt bedienbar): 7 Funde. Kleinere Funde/Best Practice: 15 Funde. Am schwaechsten aufgestellt: Meeting-Lobby (fehlende ARIA-Details).

## 1) PWA-Install-Banner + Modal (base.html)
Gut: Modal-Skelett role=dialog aria-modal=true aria-labelledby=pwaModalTitle (Zeile 845); Fokus-Trap mit Escape-Handler (1001-1012), Fokus-Restore auf Trigger (968); dekorative SVG-Icons aria-hidden=true (859/860); Tabs mit role=tablist/tab/aria-controls/aria-selected/tabpanel (850-856, 876, 895); Close-Button aria-label=Close (847).

Mittelschwere Funde:
1. Tab-Tastaturnavigation fehlt - base.html:851-853, 991-993. Kein Roving-Tabindex, keine Pfeiltasten-Navigation zwischen Tabs. WCAG 2.1.1 A / ARIA-APG.
2. Fokus-Restore laeuft ins Leere, wenn Modal aus dem Banner geoeffnet wird - base.html:1015. bannerOpen.click ruft erst dismissBanner() (Banner display:none), dann openModal(bannerOpen); closeModal() versucht dann einen unsichtbaren Button zu fokussieren. WCAG 2.4.3 A.
3. Aktive Tab-Farbe unter WCAG-AA-Kontrast - base.html:387. .pwa-tab.active color #3498db auf weiss ~3.15:1, noetig 4.5:1. WCAG 1.4.3 AA.
4. Demo-User-Banner nutzt Landmark-Rolle falsch - base.html:455. role=banner fuer Session-Hinweis statt role=status/alert. WCAG 4.1.2 A / 1.3.1 A.

Kleinere Funde: 5. Kein sichtbarer Fokus-Indikator auf .pwa-tab/.pwa-modal-close/.pwa-banner-btns .btn (382-402). 6. Banner sollte role=status statt role=complementary haben, da er dynamisch nach 4s erscheint (911-918, 1035). 7. Zahlen-Kreise .pwa-step-num Kontrast ~3.15:1, aber aria-hidden (394, unkritisch da SR-ausgeblendet).

## 2) Pricing-Sektion (landing.html)
Gut: klare Ueberschriftenhierarchie h1/h2/h3 lueckenlos; CTAs echte <a href> mit min-height 44px; Anker id=pricing; Grid-Layout reflowt sauber.

Mittelschwerer Fund:
8. Feature-Checkmark-Kontrast unterhalb AA - landing.html:146. .lp-plan ul li::before content Haken color #28a745 auf weiss ~3.05:1, noetig 4.5:1. WCAG 1.4.3 AA.

Kleinere Funde: 9. Sektionen sind div.lp-section statt section-Elemente (32-47, 205, 225, 275, 307, 367, 380). 10. Preis-Blau #007bff (78, 112, 129) ~4.55:1, knapp ueber Grenze ohne Puffer. 11. Emoji-Icons im Problem-Grid ohne aria-hidden (210, 213, 216, 219).

## 3) Invoice-Detailseite (invoice_detail.html)
Gut: Formular-Labels sauber label-for (179, 183); required-Attribut (180); Payer-Edit-Toggle mit aria-expanded (164, 304); Profile-Warning role=alert (121); Items-Tabelle mit aria-label und th scope=col (198-204); Actions als echte button/a-Elemente.

Mittelschwere Funde:
12. Alle drei Status-Pills schlagen im Light-Mode AA-Kontrast (12-14): Draft #6b7280 auf ~#ececef ~4.06:1; Sent #2563eb auf ~#e8ecfa ~3.91:1; Paid #16a34a auf ~#e6f3ec ~2.58:1 (besonders kritisch). Dark-Mode ist ok, Light-Mode ist Default. WCAG 1.4.3 AA.
13. Disabled PDF-Button ist keine echte Steuerung - invoice_detail.html:247-250. span.action-btn.disabled mit pointer-events:none, nicht fokussierbar, keine ARIA-Rolle. Sollte echtes button disabled sein. WCAG 4.1.2 A.
14. Zurueck-Link ohne Text-Dekoration - invoice_detail.html:109. text-decoration:none + grau, ohne Farbe allein nicht als Link erkennbar. WCAG 1.4.1.

Kleinere Funde: 15. Icon-Emojis in Action-Buttons duplizieren Text, sollten aria-hidden (236, 242, 248, 257, 268, 274, 281, 288). 16. Mobile Card-Layout thead per display:none versteckt Spalten-Kontext fuer AT (78). 17. Dauer im Mobile-Layout via ::after content attr(data-duration), von manchen aelteren SR nicht vorgelesen (92, 96-102). 18. Payer-Toggle-Button nutzt reine Icon-Zeichen als Text ohne aria-hidden (164, 305).

## 4) Meeting-Pre-Join-Lobby (room.html) - schwaechster Bereich
Gut: Dialog-Wrapper role=dialog aria-modal=true aria-labelledby=lobby-title (258); Join-Button erhaelt initialen Fokus (1773); 16:9-Vorschau + Kamera/Mikro-Toggles mit lesbaren Labels; Fallback auf Audio-Only mit sichtbarer Fehlermeldung (1673-1682).

Mittelschwere Funde:
19. Kein Fokus-Trap in der Lobby - room.html:258-279. Trotz aria-modal=true kein Tab-Trap, Fokus kann zu verdeckten Elementen springen. WCAG 2.4.3 A.
20. Kein sichtbarer Fokus auf .lobby-toggle und #lobby-join - room.html:231-250. Keine eigenen focus/focus-visible-Regeln. WCAG 2.4.7 AA.
21. Fehler-Region ohne Live-Region-Semantik - room.html:275. div#lobby-err ohne role=alert/aria-live, SR-Nutzer erfaehrt nichts von Kamera-Problemen. WCAG 4.1.3 AA.
22. Join-Button-Kontrast - room.html:245-246. Weiss auf #27ae60 ~3.15:1, noetig 4.5:1 (kein Large-Text). WCAG 1.4.3 AA.
23. Toggle-Buttons ohne aria-pressed - room.html:269-270. Mikro/Kamera-Toggles ohne aria-pressed=true/false. WCAG 4.1.2 A.

Kleinere Funde: 24. Lobby-Titel ist div statt heading (260). 25. #lobby-name-row Text #888 auf #242424 Kontrast ~4.7:1, knapp AA (239-242). 26. Emojis vor Button-Texten ohne aria-hidden (260, 269-270, 277, 296, 315-318). 27. Kein Escape-Handler in der Lobby, tolerierbar da kein sinnvoller Cancel (258-279). 28. video#lobby-video ohne aria-label (264). 29. html lang hart auf "de", ignoriert LANGUAGE_CODE (Zeile 2).

## Empfohlene Priorisierung
Sofort: Meeting-Lobby Fokus-Trap (#19), Fehler-Live-Region (#21), sichtbarer Fokus (#20); Invoice Status-Pill-Kontraste Light-Mode (#12).
Bald: PWA-Modal Tab-Tastaturnavigation (#1), Fokus-Restore-Bug (#2), Aktive-Tab-Kontrast (#3), Demo-User-Banner-Landmark (#4), Join-Button-Kontrast (#22), Feature-Check-Kontrast (#8), Disabled PDF-Button (#13), Zurueck-Link ohne Underline (#14), Toggle-Buttons aria-pressed (#23).
Best Practice: Fokus-Stile global (#5, #20), role=status PWA-Banner (#6), section-Elemente Landing (#9), Icon-Emojis aria-hidden (#11, #15, #26), Mobile-Layout thead visuell verstecken statt display:none (#16), Duration SR-sicher (#17), Lobby-Titel als Heading (#24), Video aria-label (#28), lang dynamisch (#29).
