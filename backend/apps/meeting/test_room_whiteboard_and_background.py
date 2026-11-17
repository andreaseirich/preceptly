"""Meeting-Raum: Radierer und Rückkehr aus dem Hintergrund.

Meldung von Andreas nach einem Test mit dem Handy, 17.11.2026: "Das Radiergummi radiert nicht die Zeichnungen, sondern malt mit
hellgrau." Und: Wechselt man auf dem iPhone aus dem Browser in eine andere App, geht die Verbindung verloren und kommt erst
zurück, wenn der Browser wieder geöffnet wird.

Das Verhalten wurde im Browser geprüft (Stift und Radierer auf weißem Blatt und auf einem farbigen PDF-Hintergrund, alte gegen
neue Fassung; Verbindungsaufbau, Rückkehr, Mikrofon-Wechsel und Wachhalter mit einem Fake-Socket, dazu Fehler gezielt eingebaut).
Das ist nicht Teil der CI. Die Tests hier sichern, was in der CI möglich ist: dass die Korrekturen in der ausgelieferten Seite
stehen, je eine Prüfung pro behobenem Fehler.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.meeting.test_room_robustness import make_room
from apps.portal.models import ParentStudentLink, PortalUser

User = get_user_model()


def between(html, start, end):
    """Text von der Marke `start` bis zur Marke `end` (beide müssen genau so in der Seite stehen)."""
    begin = html.index(start)
    return html[begin : html.index(end, begin)]


class RoomPageTestCase(TestCase):
    def setUp(self):
        self.tutor, self.contract, self.room = make_room("wb_tutor")
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


class EraserTest(RoomPageTestCase):
    def test_strokes_are_drawn_on_their_own_layer_above_the_page(self):
        html = self.tutor_page()

        redraw = between(html, "function redrawAll() {", "let _wbRedrawQueued")
        self.assertIn("wbStrokes.forEach(s => drawStroke(s, wbLayerCtx))", redraw)
        self.assertNotIn("wbStrokes.forEach(drawStroke)", html)  # früher: direkt auf dem Blatt
        # erst Blatt oder PDF, dann die Ebene mit den Strichen darüber
        self.assertLess(
            redraw.index("wbBackground.img"), redraw.index("wbCtx.drawImage(wbLayer, 0, 0)")
        )
        # der Strich, den der Radierer gerade zieht, wirkt schon vor dem Loslassen
        self.assertIn(
            "if (wbCurrentStroke && wbCurrentStroke.erase) drawStroke(wbCurrentStroke, wbLayerCtx);",
            redraw,
        )

    def test_drawing_a_stroke_never_touches_the_main_canvas_with_the_eraser(self):
        html = self.tutor_page()

        # drawStroke arbeitet auf dem übergebenen Kontext, nicht fest auf der Hauptfläche
        draw = between(html, "function drawStroke(stroke, ctx) {", "function clearWhiteboard(")
        self.assertIn("ctx = ctx || wbCtx;", draw)
        self.assertNotIn("wbCtx.", draw)
        self.assertIn("'destination-out'", draw)
        # beim Ziehen des Radierers wird die Ebene neu aufgebaut, statt auf das Blatt zu malen
        move = between(html, "function wbContinueStroke(e) {", "function wbEndStroke()")
        self.assertNotIn("destination-out", move)
        self.assertIn("if (s.erase) { requestWbRedraw(); return; }", move)
        # nach dem Loslassen steht der endgültige Stand
        end = between(html, "function wbEndStroke() {", "function drawStroke(")
        self.assertIn("if (wasErase) redrawAll();", end)

    def test_a_stroke_of_the_other_side_goes_through_the_same_redraw(self):
        html = self.tutor_page()

        branch = between(html, 'if (msg.action === "stroke") {', 'else if (msg.action === "clear")')
        self.assertIn("redrawAll();", branch)
        self.assertNotIn(
            "drawStroke(msg.stroke)", branch
        )  # früher: ohne Zoom und Verschiebung gezeichnet

    def test_the_layer_exists_in_both_pages(self):
        for name, html in {"Tutor": self.tutor_page(), "Schüler": self.student_page()}.items():
            with self.subTest(rolle=name):
                self.assertIn('const wbLayer    = document.createElement("canvas");', html)


class ReturnFromBackgroundTest(RoomPageTestCase):
    def test_coming_back_checks_the_connection_at_once(self):
        html = self.tutor_page()

        self.assertIn('document.addEventListener("visibilitychange"', html)
        resume = between(
            html,
            "async function resumeAfterBackground() {",
            'document.addEventListener("visibilitychange"',
        )
        # kein Neuaufbau und kein neues Mikrofon, wenn man das Meeting bewusst verlassen hat
        self.assertIn("if (!ws || _intentionalClose || _leaving) return;", resume)
        self.assertIn("if (ws.readyState !== WebSocket.OPEN) { reconnectNow(); return; }", resume)
        # nur nach einer längeren Pause nachfragen, ein Wechsel von unter 2 Sekunden übersteht die Verbindung
        self.assertIn("if (away < 2000) return;", resume)
        # ein toter Socket antwortet nicht: nach 2 Sekunden ohne Pong neu verbinden (Zähler statt Zeitstempel)
        self.assertIn("_pongCount === before", resume)
        self.assertIn("2000);", resume)

    def test_reconnecting_does_not_wait_for_the_backoff_and_leaves_no_second_socket(self):
        html = self.tutor_page()

        reconnect = between(html, "function reconnectNow() {", "// Nach einer Pause")
        self.assertIn("old.onopen = old.onmessage = old.onclose = old.onerror = null;", reconnect)
        self.assertIn("_reconnectDelay = 1000;", reconnect)
        self.assertIn("connectWS();", reconnect)
        self.assertIn("if (_intentionalClose || _leaving) return;", reconnect)
        self.assertIn('window.addEventListener("online"', html)

    def test_a_silent_socket_is_noticed_without_waiting_for_the_browser(self):
        html = self.tutor_page()

        heartbeat = between(html, "_wsHeartbeat = setInterval(() => {", "}, 3000);")
        self.assertIn(
            "!document.hidden && Date.now() - _lastPong > 15000", heartbeat
        )  # im Hintergrund nicht auswerten
        self.assertIn("reconnectNow()", heartbeat)
        self.assertIn('case "pong":', html)
        self.assertIn("_pongCount++;", html)

    def test_microphone_and_camera_are_fetched_again_when_the_system_ended_them(self):
        html = self.tutor_page()

        refresh = between(
            html,
            "async function refreshLocalTrack(kind) {",
            "async function resumeAfterBackground()",
        )
        self.assertIn(
            'if (old.readyState === "live" && !old.muted) return;', refresh
        )  # intakte Spur bleibt
        self.assertIn("if (!old) return;", refresh)  # nichts anfordern, was nie erlaubt war
        self.assertIn(
            'fresh.enabled = kind === "audio" ? micActive : camActive;', refresh
        )  # stumm bleibt stumm
        self.assertIn("sender.replaceTrack(fresh)", refresh)
        # die Lobby und das erneute Holen nutzen dieselben Einstellungen
        lobby = between(html, "async function initLobby() {", "const getMedia")
        self.assertIn("const AUDIO = MEDIA_AUDIO;", lobby)

    def test_the_screen_is_kept_awake_while_the_meeting_runs(self):
        html = self.tutor_page()

        self.assertIn('navigator.wakeLock.request("screen")', html)
        # beim Beitritt angefordert, nach jeder Rückkehr aus dem Hintergrund erneut (das System gibt ihn dort frei)
        self.assertIn("requestWakeLock();\n    connectWS();\n}", html)
        self.assertIn(
            "requestWakeLock();",
            between(html, "async function resumeAfterBackground() {", "document.addEventListener"),
        )

    def test_the_lobby_tells_phone_users_what_an_app_switch_does(self):
        for name, html in {"Tutor": self.tutor_page(), "Schüler": self.student_page()}.items():
            with self.subTest(rolle=name):
                self.assertIn(
                    '<div id="lobby-phone-hint" hidden>', html
                )  # nur auf Touchgeräten sichtbar
                self.assertIn("Wechselst du in eine andere App", html)
                self.assertIn('window.matchMedia("(pointer: coarse)")', html)
