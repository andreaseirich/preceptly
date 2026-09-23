"""Kurzlebige TURN-Zugangsdaten."""

import base64
import hashlib
import hmac
import json
import time

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.meeting.models import MeetingRoom
from apps.meeting.tests_meeting import make_contract, make_session, make_user
from apps.meeting.turn_auth import ice_servers

SECRET = "test-shared-secret"


def _expected_password(username):
    digest = hmac.new(SECRET.encode(), username.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


@override_settings(
    MEETING_STUN_URLS=["stun:stun.example.com:3478"],
    MEETING_TURN_URLS=["turn:turn.example.com:3478"],
    TURN_USER="preceptly",
    TURN_CREDENTIAL="statisches-passwort",
)
class IceServersTest(TestCase):
    @override_settings(TURN_STATIC_AUTH_SECRET="")
    def test_without_secret_the_static_user_is_used(self):
        servers = ice_servers()

        self.assertEqual(servers[0], {"urls": "stun:stun.example.com:3478"})
        self.assertEqual(servers[1]["username"], "preceptly")
        self.assertEqual(servers[1]["credential"], "statisches-passwort")

    @override_settings(TURN_STATIC_AUTH_SECRET=SECRET, TURN_CREDENTIAL_TTL_SECONDS=3600)
    def test_with_secret_credentials_expire_and_verify(self):
        before = time.time()
        servers = ice_servers()
        turn = servers[1]

        expires_at, _, suffix = turn["username"].partition(":")
        self.assertTrue(suffix)
        self.assertNotIn("statisches-passwort", json.dumps(servers))
        # Ablauf liegt eine Stunde in der Zukunft (kleine Toleranz für die Laufzeit).
        self.assertAlmostEqual(int(expires_at), int(before) + 3600, delta=5)
        self.assertEqual(turn["credential"], _expected_password(turn["username"]))

    @override_settings(TURN_STATIC_AUTH_SECRET=SECRET)
    def test_each_call_returns_fresh_credentials(self):
        first = ice_servers()[1]["username"]
        second = ice_servers()[1]["username"]

        self.assertNotEqual(first, second)

    @override_settings(TURN_STATIC_AUTH_SECRET=SECRET)
    def test_room_page_serves_ephemeral_credentials(self):
        tutor = make_user()
        lesson = make_session(make_contract(tutor))
        room = MeetingRoom.objects.create(lesson=lesson, is_active=True)
        self.client.force_login(tutor)

        response = self.client.get(reverse("meeting:room", kwargs={"token": room.token}))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertNotIn("statisches-passwort", body)
        self.assertIn("turn.example.com", body)
