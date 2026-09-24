"""Content-Security-Policy: welche Quellen eine Seite laden darf.

Die Richtlinie startet im Melde-Modus (``Content-Security-Policy-Report-Only``):
Der Browser blockiert nichts, meldet Verstöße aber an ``/csp-report/``. So lässt
sich vor dem Scharfschalten sehen, was eine echte Sperre kaputt machen würde —
gerade im Videoraum, wo ein Fehlschlag ein laufendes Meeting beenden würde.

Skripte laufen nur mit Nonce: Jede Antwort bekommt eine neue Zufallszahl, die
Vorlagen über ``{{ csp_nonce }}`` an jedes ``<script>`` setzen. Eingeschleuster
Code kennt sie nicht. Inline-Handler (``onclick="…"``) können keine Nonce tragen;
ihre Aufgabe übernimmt ``static/js/actions.js`` über Daten-Attribute.

Umschalten auf Durchsetzung: Umgebungsvariable ``CSP_REPORT_ONLY=0``.
"""

import secrets

from django.conf import settings

# Der gesetzlich vorgeschriebene Widerrufs-Button von e-Recht24 braucht mehrere
# fremde Quellen. Ermittelt am 24.09.2026 im Melde-Modus und aus den Skripten
# selbst - das Absenden lässt sich nicht gefahrlos ausprobieren:
#   - Skripte und Stylesheet des Fensters kommen vom CDN,
#   - der abgeschickte Widerruf geht an eine ANDERE Adresse (die API),
#   - das Formular bindet Friendly Captcha ein: Widget von jsDelivr, Rätsel vom
#     Friendly-Captcha-Server, gelöst per WebAssembly in einem Blob-Worker.
# Fehlt eine davon, öffnet sich das Fenster zwar, aber der Widerruf kommt nie an.
ERECHT24_CDN = "https://widerrufsbutton-cdn.e-recht24.de"
ERECHT24_API = "https://widerrufsbutton.e-recht24.de"
FRIENDLY_CAPTCHA_API = "https://api.friendlycaptcha.com"
JSDELIVR = "https://cdn.jsdelivr.net"

POLICY_DIRECTIVES = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "font-src 'self' data:",
    # Inline-Styles stecken derzeit in fast jeder Vorlage.
    f"style-src 'self' 'unsafe-inline' {ERECHT24_CDN}",
    f"connect-src 'self' {ERECHT24_CDN} {ERECHT24_API} {FRIENDLY_CAPTCHA_API}",
    f"frame-src {ERECHT24_CDN}",
    # pdf.js und Friendly Captcha legen ihre Arbeitsprozesse als Blob an.
    "worker-src 'self' blob:",
]

# Skripte, gestaffelt nach Browsergeneration („Strict CSP"):
#   - Aktuelle Browser: nur Skripte mit Nonce und was diese per JavaScript
#     nachladen ('strict-dynamic'). Hostliste und 'unsafe-inline' zählen dann
#     nicht - ein eingeschleustes <script src="…jsdelivr…"> hat keine Nonce und
#     wird abgewiesen. Das e-Recht24-Skript trägt die Nonce und darf deshalb
#     Fenster und Captcha nachladen, in welcher Version auch immer.
#   - Ältere Browser ohne 'strict-dynamic': Nonce plus Hostliste.
#   - Uralte Browser ohne Nonces: Hostliste plus 'unsafe-inline'.
# 'wasm-unsafe-eval' erlaubt nur das Übersetzen von WebAssembly (Captcha-
# Rechenkern), kein eval() von JavaScript.
SCRIPT_FALLBACK_SOURCES = ["'self'", ERECHT24_CDN, JSDELIVR, "'unsafe-inline'"]

REPORT_PATH = "/csp-report/"


def new_nonce():
    return secrets.token_urlsafe(16)


def policy_value(nonce=None):
    script = ["script-src"]
    if nonce:
        # 'strict-dynamic' nur mit Nonce: ohne sie wäre gar nichts mehr erlaubt.
        script += [f"'nonce-{nonce}'", "'strict-dynamic'"]
    script += ["'wasm-unsafe-eval'", *SCRIPT_FALLBACK_SOURCES]
    return "; ".join([*POLICY_DIRECTIVES, " ".join(script), f"report-uri {REPORT_PATH}"])


class ContentSecurityPolicyMiddleware:
    """Vergibt je Anfrage eine Nonce und setzt die Richtlinie auf HTML-Antworten."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.header = (
            "Content-Security-Policy-Report-Only"
            if getattr(settings, "CSP_REPORT_ONLY", True)
            else "Content-Security-Policy"
        )

    def __call__(self, request):
        # Vor der View setzen: Vorlagen lesen sie über den Context-Processor.
        request.csp_nonce = new_nonce()
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if content_type.startswith("text/html") and not response.has_header(self.header):
            response[self.header] = policy_value(request.csp_nonce)
        return response
