"""Tests for Erecht24PushView – webhook signature verification."""

import hashlib
import hmac
import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse

TEST_SECRET = "test-push-secret-value"


def _signed_post(client, payload, secret=TEST_SECRET, corrupt=False):
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if corrupt:
        sig = "0" * len(sig)
    return client.post(
        reverse("core:erecht24_push"),
        data=body,
        content_type="application/json",
        HTTP_X_ER24_SIGNATURE=sig,
    )


class Erecht24PushViewSecretTest(TestCase):
    def setUp(self):
        self.client = Client()

    @override_settings(ERECHT24_PUSH_SECRET=TEST_SECRET)
    def test_valid_ping_not_rejected(self):
        """Valid HMAC signature with ERECHT24_PUSH_SECRET must not return 403."""
        response = _signed_post(
            self.client, {"erecht24_type": "ping", "erecht24_secret": TEST_SECRET}
        )
        self.assertNotEqual(response.status_code, 403)

    @override_settings(ERECHT24_PUSH_SECRET="")
    def test_missing_secret_returns_403(self):
        """Empty ERECHT24_PUSH_SECRET must reject the request."""
        response = _signed_post(self.client, {"erecht24_type": "ping"})
        self.assertEqual(response.status_code, 403)

    @override_settings(ERECHT24_PUSH_SECRET=TEST_SECRET)
    def test_wrong_signature_returns_403(self):
        """Corrupted HMAC signature must be rejected."""
        response = _signed_post(self.client, {"erecht24_type": "ping"}, corrupt=True)
        self.assertEqual(response.status_code, 403)
