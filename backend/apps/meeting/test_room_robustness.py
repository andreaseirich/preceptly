"""Meeting-Raum: Verlassen, Medien ohne eigene Spuren und Whiteboard-Text.

Meldung von Andreas, 29.10.2026: "Man kann das Meeting nicht verlassen, man sieht und hört sich gegenseitig nicht, trotz
dass der Schüler schon drin war, und auch die Textfelder auf dem Whiteboard bleiben nicht auf dem Whiteboard."

Das Verhalten im Browser wurde in Headless-Chrome gegen die alte und die neue Fassung geprüft (hängendes Netz beim
Verlassen, zwei Teilnehmer mit echter WebRTC-Verbindung, sieben Szenarien des Text-Werkzeugs). Die Tests hier sichern, was in
der CI möglich ist: das Server-Logformat der Diagnose und, dass die Korrekturen in der ausgelieferten Seite stehen.
Letzteres sind bewusst einfache Prüfungen auf Textstellen, je eine pro behobenem Fehler.
"""

import uuid
from datetime import date, time
from decimal import Decimal

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Session
from apps.meeting.consumers import MeetingConsumer, format_diag
from apps.meeting.models import MeetingRoom
from apps.portal.models import ParentStudentLink, PortalUser

User = get_user_model()


def make_room(tutor_name):
    tutor = User.objects.create_user(username=tutor_name, password="pw")
    UserProfile.objects.update_or_create(user=tutor, defaults={"subscription_tier": "pro"})
    contract = Contract.objects.create(
        user=tutor,
        first_name="Lea",
        last_name="Schmidt",
        hourly_rate=Decimal("30.00"),
        start_date=date(2025, 1, 1),
    )
    lesson = Session.objects.create(
        contract=contract, date=date(2026, 10, 29), start_time=time(14, 0), duration_minutes=60
    )
    return tutor, contract, MeetingRoom.objects.create(lesson=lesson, is_active=True)


class FormatDiagTest(TestCase):
    def test_known_fields_become_one_line(self):
        line = format_diag(
            {
                "event": "connected",
                "state": "connected",
                "route": "relay/host/udp",
                "local_audio": 1,
                "local_video": 0,
                "remote_tracks": 2,
            }
        )

        self.assertEqual(
            line,
            "event=connected state=connected route=relay/host/udp local_audio=1 local_video=0 remote_tracks=2",
        )

    def test_unknown_fields_are_dropped(self):
        line = format_diag({"event": "join", "token": "geheim", "sdp": "v=0..."})

        self.assertEqual(line, "event=join")

    def test_line_breaks_and_odd_characters_cannot_reach_the_log(self):
        line = format_diag(
            {"event": "x\nINFO gefälscht: admin angemeldet\r\n", "state": "a b;c<d>"}
        )

        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)
        self.assertNotIn(" ", line.split("event=", 1)[1].split(" state=")[0])
        self.assertIn("state=abcd", line)

    def test_numbers_are_clamped_and_booleans_ignored(self):
        line = format_diag({"local_audio": 500, "local_video": -3, "remote_tracks": True})

        self.assertEqual(line, "local_audio=99 local_video=0")

    def test_long_text_is_cut_and_other_types_ignored(self):
        line = format_diag({"event": "a" * 200, "route": ["list"], "state": None, "ice": {"a": 1}})

        self.assertEqual(line, "event=" + "a" * 30)

    def test_empty_message(self):
        self.assertEqual(format_diag({}), "")


class DiagMessageTest(TransactionTestCase):
    """Der Server nimmt eine Diagnosemeldung entgegen und schreibt sie ins Log, sonst nichts."""

    def setUp(self):
        self.tutor, self.contract, self.room = make_room("diag_tutor")
        self.portal = PortalUser.objects.create(
            user=User.objects.create_user(username="diag_portal", password="pw"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(parent=self.portal, contract=self.contract, is_active=True)
        MeetingConsumer._rooms_data.clear()
        MeetingConsumer._user_channels_data.clear()
        MeetingConsumer._user_peers_data.clear()

    async def _connect(self):
        communicator = WebsocketCommunicator(
            MeetingConsumer.as_asgi(), f"/ws/meeting/{self.room.token}/"
        )
        communicator.scope["user"] = self.tutor
        communicator.scope["session"] = {}
        communicator.scope["url_route"] = {"kwargs": {"token": str(self.room.token)}}
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.send_json_to(
            {"type": "join", "name": "Tutor", "is_tutor": True, "user_token": "x"}
        )
        joined = await communicator.receive_json_from()
        self.assertEqual(joined["type"], "joined")
        return communicator

    async def test_a_diag_message_is_logged_with_role_and_state(self):
        communicator = await self._connect()

        with self.assertLogs("apps.meeting.consumers", level="INFO") as logs:
            await communicator.send_json_to(
                {
                    "type": "diag",
                    "event": "no_media_10s",
                    "state": "new",
                    "local_audio": 0,
                    "local_video": 0,
                }
            )
            await communicator.send_json_to({"type": "ping"})
            await communicator.receive_json_from()  # pong: Die Meldung davor ist verarbeitet

        output = "\n".join(logs.output)
        self.assertIn("Meeting diag", output)
        self.assertIn("rolle=tutor", output)
        self.assertIn("event=no_media_10s", output)
        self.assertIn("local_audio=0", output)
        self.assertNotIn(str(self.room.token), output)  # nur ein Anfang des Raum-Tokens
        await communicator.disconnect()

    async def test_a_diag_message_is_not_forwarded_to_other_participants(self):
        tutor = await self._connect()
        student = WebsocketCommunicator(
            MeetingConsumer.as_asgi(), f"/ws/meeting/{self.room.token}/"
        )
        student.scope["user"] = AnonymousUser()
        student.scope["session"] = {"portal_user_id": self.portal.pk}
        student.scope["url_route"] = {"kwargs": {"token": str(self.room.token)}}
        connected, _ = await student.connect()
        self.assertTrue(connected)
        await student.send_json_to(
            {"type": "join", "name": "Lea", "is_tutor": False, "user_token": "y"}
        )
        self.assertEqual((await student.receive_json_from())["type"], "joined")
        self.assertEqual((await tutor.receive_json_from())["type"], "peer_joined")

        await tutor.send_json_to({"type": "diag", "event": "connected", "state": "connected"})
        await tutor.send_json_to({"type": "ping"})
        self.assertEqual((await tutor.receive_json_from())["type"], "pong")

        self.assertTrue(await student.receive_nothing())  # die Diagnose bleibt beim Server
        await tutor.disconnect()
        await student.disconnect()


class RoomPageFixesTest(TestCase):
    """Die Korrekturen stehen in der ausgelieferten Seite (Tutor und Schüler)."""

    def setUp(self):
        self.tutor, self.contract, self.room = make_room("fix_tutor")
        self.url = reverse("meeting:room", kwargs={"token": str(self.room.token)})

    def tutor_page(self):
        self.client.force_login(self.tutor)
        return self.client.get(self.url).content.decode()

    def student_page(self):
        portal = PortalUser.objects.create(
            user=User.objects.create_user(username=f"p{uuid.uuid4().hex[:6]}", password="pw"),
            role="student",
            tutor=self.tutor,
        )
        ParentStudentLink.objects.create(parent=portal, contract=self.contract, is_active=True)
        session = self.client.session
        session["portal_user_id"] = portal.pk
        session.save()
        return self.client.get(self.url).content.decode()

    def pages(self):
        return {"Tutor": self.tutor_page(), "Schüler": self.student_page()}

    def test_leaving_does_not_wait_for_the_network(self):
        for who, html in self.pages().items():
            with self.subTest(wer=who):
                start = html.index("async function hangUp()")
                body = html[start : html.index("function getCookie(name)", start)]
                self.assertIn(
                    "if (_leaving) return;", body
                )  # mehrfaches Klicken beendet nur einmal
                self.assertIn("keepalive: true", body)  # die Anfrage überlebt den Seitenwechsel
                self.assertIn("Promise.race", body)  # höchstens 2 Sekunden Wartezeit
                self.assertNotIn("await fetch(END_URL", body)  # früher: wartete ohne Ende
                self.assertIn("localStream.getTracks().forEach(t => t.stop())", body)  # Kamera aus

    def test_a_participant_without_camera_or_microphone_can_still_receive(self):
        for who, html in self.pages().items():
            with self.subTest(wer=who):
                self.assertIn('pc.addTransceiver("audio", { direction: "recvonly" })', html)
                self.assertIn('pc.addTransceiver("video", { direction: "recvonly" })', html)

    def test_remote_tracks_without_a_stream_are_collected(self):
        html = self.tutor_page()

        self.assertIn("new MediaStream()", html)
        self.assertIn("peer.stream.addTrack(track)", html)

    def test_the_status_line_does_not_claim_a_connection_that_does_not_exist(self):
        html = self.tutor_page()

        self.assertIn("Verbindung wird aufgebaut", html)
        self.assertIn('["connected", "completed"].includes(peerState(p.pc))', html)

    def test_every_participant_gets_a_tile_with_a_status_at_once(self):
        html = self.tutor_page()

        self.assertIn("function ensurePeerTile(peerId, name)", html)
        self.assertIn('setPeerStatus(peerId, "Verbinde …")', html)
        self.assertIn(".video-tile .tile-status", html)

    def test_the_lobby_tells_the_truth_about_missing_devices(self):
        for who, html in self.pages().items():
            with self.subTest(wer=who):
                self.assertIn("Kein Zugriff auf Kamera und Mikrofon", html)
                self.assertIn("🎤 nicht verfügbar", html)
                self.assertIn("📷 nicht verfügbar", html)
                self.assertIn("_lobbyMicOn = hasAudio;", html)
                # ohne Spur lässt sich nichts umschalten
                self.assertIn(
                    "function toggleMic() {\n    if (!localStream || !localStream.getAudioTracks().length) return;",
                    html,
                )

    def test_the_text_field_is_committed_wherever_the_user_clicks(self):
        html = self.tutor_page()

        self.assertIn("function commitTextOverlay()", html)
        # Capture-Phase am Dokument: wirkt auch bei Buttons ohne Fokus (Firefox, Safari auf dem Mac)
        self.assertIn("document.addEventListener('pointerdown'", html)
        self.assertIn("}, true);", html)
        # Tab-Wechsel und Verlassen bestätigen das Feld zuerst
        switch = html[html.index("function switchTab(name, btn) {") :][:200]
        self.assertIn("commitTextOverlay();", switch)
        hang = html[html.index("async function hangUp()") :][:400]
        self.assertIn("commitTextOverlay();", hang)

    def test_an_empty_blur_does_not_close_a_freshly_opened_field(self):
        html = self.tutor_page()

        self.assertIn("if (wbTextOpen && input.value.trim()) commitTextOverlay();", html)

    def test_a_sync_on_joining_never_replaces_what_is_already_drawn(self):
        html = self.tutor_page()

        start = html.index('msg.action === "state_sync"')
        branch = html[start : html.index('document.addEventListener("keydown"', start)]
        self.assertIn("mergeStrokes(", branch)
        self.assertNotIn("wbStrokes =", branch)
        self.assertNotIn("clearWbBackground", branch)

    def test_the_browser_reports_its_media_state_for_the_log(self):
        html = self.tutor_page()

        self.assertIn("function sendDiag(info)", html)
        self.assertIn('sendConnectionDiag(peerId, pc, "no_media_10s")', html)
        self.assertIn("sendLocalMediaDiag();", html)
