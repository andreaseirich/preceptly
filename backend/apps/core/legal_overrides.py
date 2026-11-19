"""Anpassungen am erzeugten Teil der Datenschutzerklärung (eRecht24).

eRecht24 erzeugt den allgemeinen Teil der Erklärung aus Bausteinen und kennt nicht jede Einrichtung. Wo ein Baustein für
Preceptly nicht stimmt, ersetzen wir ihn hier beim Ausliefern. Der Zwischenspeicher (`erecht24_service`) und die Webhooks von
eRecht24 bleiben unberührt: Ändert eRecht24 seinen Text, gilt unsere Fassung des betroffenen Abschnitts weiter.

Sicherheitsnetz: Wird die Überschrift nicht genau einmal gefunden (eRecht24 hat sie umbenannt oder verdoppelt), bleibt der erzeugte
Text unverändert und es gibt eine Warnung im Log. Die Seite fällt dann nie aus.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Cloudflare ist für preceptly.de nur der DNS-Dienst (Nameserver). Der Seitenaufruf läuft direkt zum Hoster Railway, nicht
# über das Netzwerk von Cloudflare (geprüft an den Antwortkopfzeilen: "server: railway-hikari", kein "cf-ray").
# Der erzeugte Baustein beschreibt dagegen ein Content Delivery Network, das den Datenverkehr durchleitet.
CLOUDFLARE_DNS = {
    "de": (
        "<h3>Cloudflare</h3>"
        "<p>Wir nutzen für die Domain preceptly.de den DNS-Dienst „Cloudflare“. Anbieter ist die Cloudflare Inc., "
        "101 Townsend St., San Francisco, CA 94107, USA (im Folgenden „Cloudflare“).</p>"
        "<p>Cloudflare beantwortet die DNS-Anfragen zu unserer Domain, also die Übersetzung des Namens preceptly.de in die "
        "Adresse unseres Servers. Dabei verarbeitet Cloudflare technisch bedingt die IP-Adresse des anfragenden DNS-Servers "
        "(in der Regel der Ihres Internetanbieters oder DNS-Dienstes). Der Datenverkehr zwischen Ihrem Browser und unserer "
        "Website läuft nicht über das Netzwerk von Cloudflare, sondern direkt zu unserem Hoster (siehe oben).</p>"
        "<p>Der Einsatz beruht auf unserem berechtigten Interesse an einer zuverlässigen und sicheren Erreichbarkeit unserer "
        "Website (Art. 6 Abs. 1 lit. f DSGVO). Die Datenübertragung in die USA wird auf die Standardvertragsklauseln der "
        "EU-Kommission gestützt. Das Unternehmen ist zudem nach dem EU-US Data Privacy Framework (DPF) zertifiziert. Weitere "
        "Informationen: https://www.cloudflare.com/privacypolicy/ .</p>"
    ),
    "en": (
        "<h3>Cloudflare</h3>"
        "<p>We use the DNS service “Cloudflare” for the domain preceptly.de. The provider is Cloudflare Inc., 101 Townsend "
        "St., San Francisco, CA 94107, USA (hereinafter “Cloudflare”).</p>"
        "<p>Cloudflare answers the DNS requests for our domain, that is, it translates the name preceptly.de into the address "
        "of our server. For this, Cloudflare technically processes the IP address of the requesting DNS server (usually that "
        "of your internet provider or DNS service). Traffic between your browser and our website does not run through "
        "Cloudflare’s network but directly to our host (see above).</p>"
        "<p>This use is based on our legitimate interest in the reliable and secure availability of our website (Art. 6 "
        "para. 1 lit. f GDPR). Data transfers to the USA are based on the standard contractual clauses of the EU "
        "Commission. The company is also certified under the EU-US Data Privacy Framework (DPF). Further information: "
        "https://www.cloudflare.com/privacypolicy/ .</p>"
    ),
}

# Überschrift des erzeugten Bausteins je Sprache -> unser Ersatz
SECTION_OVERRIDES = {
    "de": (("h3", "Cloudflare", CLOUDFLARE_DNS["de"]),),
    "en": (("h3", "Cloudflare", CLOUDFLARE_DNS["en"]),),
}

# Die Gruppenüberschrift über dem Cloudflare-Baustein verspricht ebenfalls ein CDN. Nur die Überschrift wird getauscht, der
# Inhalt darunter (Hoster) bleibt.
HEADING_OVERRIDES = {
    "de": (("h2", "2. Hosting und Content Delivery Networks (CDN)", "2. Hosting und DNS"),),
    "en": (("h2", "2. Hosting and Content Delivery Networks (CDN)", "2. Hosting and DNS"),),
}


def replace_section(html, level, heading, replacement):
    """Ersetzt den Abschnitt ab `<level>heading</level>` bis zur nächsten Überschrift (h1 bis h3) durch `replacement`.

    `replacement` enthält seine Überschrift selbst. Gibt es die Überschrift nicht genau einmal, bleibt `html` unverändert.
    """
    pattern = re.compile(
        rf"<{level}>\s*{re.escape(heading)}\s*</{level}>.*?(?=<h[1-3][\s>]|\Z)",
        re.S,
    )
    found = len(pattern.findall(html))
    if found != 1:
        logger.warning(
            "Datenschutzerklärung: Abschnitt %r nicht angepasst, weil er %d-mal vorkommt (erwartet: 1). "
            "Hat eRecht24 die Überschrift geändert?",
            heading,
            found,
        )
        return html
    return pattern.sub(lambda match: replacement, html, count=1)


def replace_heading(html, level, old, new):
    """Tauscht den Text einer Überschrift. Gibt es sie nicht genau einmal, bleibt `html` unverändert (mit Warnung im Log)."""
    pattern = re.compile(rf"(<{level}>\s*){re.escape(old)}(\s*</{level}>)")
    found = len(pattern.findall(html))
    if found != 1:
        logger.warning(
            "Datenschutzerklärung: Überschrift %r nicht angepasst, weil sie %d-mal vorkommt (erwartet: 1). "
            "Hat eRecht24 die Überschrift geändert?",
            old,
            found,
        )
        return html
    return pattern.sub(lambda match: match.group(1) + new + match.group(2), html, count=1)


def apply_privacy_overrides(html, lang):
    """Wendet unsere Abschnittsanpassungen auf den erzeugten Text an. Leerer Text und unbekannte Sprachen bleiben unberührt."""
    if not html:
        return html
    for level, heading, replacement in SECTION_OVERRIDES.get(lang, ()):
        html = replace_section(html, level, heading, replacement)
    for level, old, new in HEADING_OVERRIDES.get(lang, ()):
        html = replace_heading(html, level, old, new)
    return html
