"""Content-Security-Policy: welche Quellen eine Seite laden darf.

Die Richtlinie startet im Melde-Modus (``Content-Security-Policy-Report-Only``):
Der Browser blockiert nichts, meldet Verstöße aber an ``/csp-report/``. So lässt
sich vor dem Scharfschalten sehen, was eine echte Sperre kaputt machen würde —
gerade im Videoraum, wo ein Fehlschlag ein laufendes Meeting beenden würde.

Umschalten auf Durchsetzung: Umgebungsvariable ``CSP_REPORT_ONLY=0``.
"""

from django.conf import settings

# e-Recht24 liefert den gesetzlich nötigen Widerrufs-Button als Fremdskript
# aus; ohne diese Quelle wäre die Schaltfläche im Fußbereich tot.
ERECHT24 = "https://widerrufsbutton-cdn.e-recht24.de"

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
    "style-src 'self' 'unsafe-inline'",
    f"script-src 'self' 'unsafe-inline' {ERECHT24}",
    f"connect-src 'self' {ERECHT24}",
    f"frame-src {ERECHT24}",
    # pdf.js legt seinen Arbeitsprozess als Blob an.
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
