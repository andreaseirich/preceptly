"""Das Portal gibt es nur auf Deutsch.

Seine Vorlagen sind fest auf Deutsch geschrieben (kein {% trans %}); nur wenige Bausteine, die es mit der Tutor-App teilt (Hinweisfenster zur
Entwicklung), sind übersetzbar. Wer die Tutor-App auf Englisch gestellt hat, bekäme im Portal deshalb eine Mischung. Diese Middleware stellt
für alle Adressen unter /portal/ die Sprache auf Deutsch (und damit auch <html lang>, Content-Language und Datumsformate). Eine englische
Portalfassung gibt es nicht und wird nirgends versprochen: Das Portal hat keine Sprachwahl, und die englische Start- und Anmeldeseite sagen es.
"""

from django.utils import translation


class PortalGermanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/portal/"):
            translation.activate("de")
            request.LANGUAGE_CODE = "de"
        return self.get_response(request)
