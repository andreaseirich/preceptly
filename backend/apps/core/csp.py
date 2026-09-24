"""Content-Security-Policy: welche Quellen eine Seite laden darf.

Die Richtlinie startet im Melde-Modus (``Content-Security-Policy-Report-Only``):
Der Browser blockiert nichts, meldet Verstöße aber an ``/csp-report/``. So lässt
sich vor dem Scharfschalten sehen, was eine echte Sperre kaputt machen würde —
gerade im Videoraum, wo ein Fehlschlag ein laufendes Meeting beenden würde.

Umschalten auf Durchsetzung: Umgebungsvariable ``CSP_REPORT_ONLY=0``.
"""

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
# jsDelivr steht bewusst als ganzer Host drin: Die Version des Widgets legt
# e-Recht24 fest (derzeit friendly-challenge@0.9.14). Ein festgenagelter Pfad
# würde das Formular beim nächsten Update stillschweigend lahmlegen. Solange
# script-src 'unsafe-inline' enthält, kostet das keinen Schutz - beim Umstieg
# auf Nonces nachschärfen.
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
    # Inline-Styles und Inline-Skripte stecken derzeit in fast jeder Vorlage.
    # Sie fallen erst weg, wenn die Vorlagen auf Nonces umgestellt sind.
    f"style-src 'self' 'unsafe-inline' {ERECHT24_CDN}",
    # 'wasm-unsafe-eval' erlaubt nur das Übersetzen von WebAssembly (für den
    # Captcha-Rechenkern), kein eval() von JavaScript.
    f"script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' {ERECHT24_CDN} {JSDELIVR}",
    f"connect-src 'self' {ERECHT24_CDN} {ERECHT24_API} {FRIENDLY_CAPTCHA_API}",
    f"frame-src {ERECHT24_CDN}",
    # pdf.js und Friendly Captcha legen ihre Arbeitsprozesse als Blob an.
    "worker-src 'self' blob:",
]

REPORT_PATH = "/csp-report/"


def policy_value():
    return "; ".join([*POLICY_DIRECTIVES, f"report-uri {REPORT_PATH}"])


class ContentSecurityPolicyMiddleware:
    """Setzt die Richtlinie auf HTML-Antworten (andere Inhalte laden nichts nach)."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.header = (
            "Content-Security-Policy-Report-Only"
            if getattr(settings, "CSP_REPORT_ONLY", True)
            else "Content-Security-Policy"
        )
        self.value = policy_value()

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if content_type.startswith("text/html") and not response.has_header(self.header):
            response[self.header] = self.value
        return response
