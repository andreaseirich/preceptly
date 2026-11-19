"""Die Datenschutzerklärung und der AVV müssen zu dem passen, was das System tatsächlich tut.

Abgleich vom 19.11.2026. Befunde: Das Meeting nutzte neben dem eigenen TURN-Server (bei Hetzner) auch die STUN-Server von Google,
die Erklärung nannte aber nur Google; der AVV nannte Hetzner nicht; das Sprach-Cookie und die Merkzettel im Browser fehlten; das
Datum war veraltet. Diese Tests binden Text und Verhalten aneinander, damit eine Änderung auf einer Seite auffällt.
"""

from django.test import TestCase
from django.urls import reverse

from apps.core.views import LEGAL_LAST_UPDATED
from apps.meeting.turn_auth import ice_servers


class MeetingServersMatchTheTextTest(TestCase):
    def urls(self):
        return [server["urls"] for server in ice_servers()]

    def test_no_ice_server_belongs_to_a_third_party(self):
        for url in self.urls():
            self.assertNotIn(
                "google", url, "die Erklärung sagt: keine IP-Adressen an externe STUN-Anbieter"
            )

    def test_stun_and_turn_run_on_the_same_host(self):
        hosts = {
            url.split(":")[1] for url in self.urls()
        }  # "stun:host:3478" und "turn:host:3478?transport=tcp"

        self.assertEqual(len(hosts), 1, f"mehrere Hosts in der ICE-Liste: {hosts}")

    def test_the_default_stun_server_is_derived_from_the_turn_url(self):
        from django.conf import settings

        self.assertEqual(
            settings.MEETING_STUN_URLS, ["stun:" + settings.MEETING_TURN_URLS[0].partition(":")[2]]
        )


class PrivacyPolicyTest(TestCase):
    def page(self, lang):
        response = self.client.get("/legal/privacy/", HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_it_names_the_relay_server_and_its_host(self):
        for lang, marker in (("de", "Relay-Server (TURN)"), ("en", "relay server (TURN)")):
            with self.subTest(lang=lang):
                html = self.page(lang)

                self.assertIn(marker, html)
                self.assertIn("Hetzner Online GmbH", html)

    def test_it_no_longer_sends_the_reader_to_google_for_the_connection(self):
        for lang in ("de", "en"):
            with self.subTest(lang=lang):
                self.assertNotIn("stun.l.google.com", self.page(lang))

    def test_it_names_the_retention_of_the_relay_servers_system_log(self):
        # Das Journal des Servers (coturn schreibt dort IP-Adressen von Verbindungsversuchen hin) ist seit 19.11.2026 auf 30 Tage
        # begrenzt: /etc/systemd/journald.conf.d/30-retention.conf. Ändert sich die Frist dort, muss der Text mit.
        self.assertIn("nach 30 Tagen automatisch gelöscht", self.page("de"))
        self.assertIn("deleted automatically after 30 days", self.page("en"))

    def test_it_says_that_chat_and_whiteboard_are_not_stored(self):
        self.assertIn("Chat-Nachrichten und Whiteboard-Zeichnungen", self.page("de"))
        self.assertIn("Chat messages and whiteboard drawings", self.page("en"))

    def test_it_discloses_that_the_revocation_widget_is_loaded_on_every_page(self):
        self.assertIn("widerrufsbutton-cdn.e-recht24.de", self.page("de"))
        self.assertIn("whether or not you use the button", self.page("en"))

    def test_it_lists_the_language_cookie_and_the_notice_in_the_browser_storage(self):
        html = self.page("de")

        self.assertIn("<code>django_language</code>", html)
        self.assertIn("sessionStorage", html)

    def test_the_language_cookie_really_is_set_and_ends_with_the_session(self):
        response = self.client.post(reverse("set_language"), {"language": "de"})

        cookie = response.cookies["django_language"]
        self.assertEqual(
            cookie["max-age"], "", "ein Sitzungs-Cookie: endet beim Schließen des Browsers"
        )

    def test_the_preceptly_section_carries_the_date_of_the_pages(self):
        # Der Kopf der Seite zeigt dasselbe Datum (aus LEGAL_LAST_UPDATED), deshalb nur den Preceptly-Teil prüfen: Er trägt sein
        # Datum von Hand in der Vorlage und war am 19.11.2026 zwei Monate veraltet.
        for lang, heading, label in (
            ("de", "Preceptly-spezifische Datenverarbeitung", "Letzte Aktualisierung"),
            ("en", "Preceptly-specific data processing", "Last updated"),
        ):
            with self.subTest(lang=lang):
                html = self.page(lang)

                section = html[html.index(heading) :]
                self.assertIn(f"{label}: {LEGAL_LAST_UPDATED}", section)


class ProcessingAgreementTest(TestCase):
    def page(self, lang):
        response = self.client.get("/legal/avv/", HTTP_ACCEPT_LANGUAGE=lang)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_hetzner_is_listed_as_sub_processor_for_the_relay(self):
        for lang, purpose in (
            ("de", "Betrieb des Relay-Servers (TURN)"),
            ("en", "Operation of the relay server (TURN)"),
        ):
            with self.subTest(lang=lang):
                html = self.page(lang)

                self.assertIn("Hetzner Online GmbH", html)
                self.assertIn(purpose, html)
                self.assertIn("6.2a", html)

    def test_the_date_is_current(self):
        day, month, year = LEGAL_LAST_UPDATED.split(".")
        english = {"11": "Nov"}.get(month)

        self.assertIn(f"Stand: {LEGAL_LAST_UPDATED}", self.page("de"))
        if english:
            self.assertIn(f"Last updated: {int(day)} {english} {year}", self.page("en"))
