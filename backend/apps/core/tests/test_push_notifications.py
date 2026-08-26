"""
Tests for push notification preferences: NotificationPreference/PushSubscription
models, push_service gating logic, and the subscribe/unsubscribe endpoints
(tutor side in apps.core, portal side in apps.portal).
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from apps.core.models import NotificationPreference, PushSubscription
from apps.core.push_service import (
    delete_push_subscription,
    is_channel_enabled,
    save_push_subscription,
    send_push_notification,
)


class NotificationPreferenceDefaultsTest(TestCase):
    """No preference row yet must behave exactly like today's always-on email."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")

    def test_no_preference_row_defaults_email_and_push_to_true(self):
        self.assertTrue(is_channel_enabled(self.user, "portal_booking", "email"))
        self.assertTrue(is_channel_enabled(self.user, "portal_booking", "push"))
        self.assertTrue(is_channel_enabled(self.user, "login_reminder", "email"))
        self.assertTrue(is_channel_enabled(self.user, "login_reminder", "push"))

    def test_explicit_preference_respected(self):
        NotificationPreference.objects.create(
            user=self.user,
            notify_portal_booking_email=False,
            notify_portal_booking_push=True,
        )
        self.assertFalse(is_channel_enabled(self.user, "portal_booking", "email"))
        self.assertTrue(is_channel_enabled(self.user, "portal_booking", "push"))

    def test_model_field_defaults_are_true(self):
        pref = NotificationPreference.objects.create(user=self.user)
        self.assertTrue(pref.notify_portal_booking_email)
        self.assertTrue(pref.notify_portal_booking_push)
        self.assertTrue(pref.notify_login_reminder_email)
        self.assertTrue(pref.notify_login_reminder_push)


class SendPushNotificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")

    def test_no_vapid_keys_configured_returns_zero_without_crash(self):
        with override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY=""):
            sent = send_push_notification(self.user, "portal_booking", "Title", "Body")
        self.assertEqual(sent, 0)

    @override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_ADMIN_EMAIL="a@b.de")
    def test_no_subscriptions_returns_zero(self):
        sent = send_push_notification(self.user, "portal_booking", "Title", "Body")
        self.assertEqual(sent, 0)

    @override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_ADMIN_EMAIL="a@b.de")
    def test_push_disabled_by_preference_skips_send(self):
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/1", p256dh="k", auth="a"
        )
        NotificationPreference.objects.create(user=self.user, notify_portal_booking_push=False)
        with patch("apps.core.push_service.webpush") as mock_webpush:
            sent = send_push_notification(self.user, "portal_booking", "Title", "Body")
        self.assertEqual(sent, 0)
        mock_webpush.assert_not_called()

    @override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_ADMIN_EMAIL="a@b.de")
    def test_sends_to_all_active_subscriptions(self):
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/1", p256dh="k1", auth="a1"
        )
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/2", p256dh="k2", auth="a2"
        )
        with patch("apps.core.push_service.webpush") as mock_webpush:
            sent = send_push_notification(
                self.user, "portal_booking", "Title", "Body", url="/dashboard/"
            )
        self.assertEqual(sent, 2)
        self.assertEqual(mock_webpush.call_count, 2)

    @override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_ADMIN_EMAIL="a@b.de")
    def test_stale_subscription_is_deleted_on_410(self):
        from pywebpush import WebPushException

        sub = PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/gone", p256dh="k", auth="a"
        )
        exc = WebPushException("gone")
        exc.response = MagicMock(status_code=410)
        with patch("apps.core.push_service.webpush", side_effect=exc):
            sent = send_push_notification(self.user, "portal_booking", "Title", "Body")
        self.assertEqual(sent, 0)
        self.assertFalse(PushSubscription.objects.filter(pk=sub.pk).exists())

    @override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_ADMIN_EMAIL="a@b.de")
    def test_non_stale_error_keeps_subscription(self):
        from pywebpush import WebPushException

        sub = PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/err", p256dh="k", auth="a"
        )
        exc = WebPushException("server error")
        exc.response = MagicMock(status_code=500)
        with patch("apps.core.push_service.webpush", side_effect=exc):
            sent = send_push_notification(self.user, "portal_booking", "Title", "Body")
        self.assertEqual(sent, 0)
        self.assertTrue(PushSubscription.objects.filter(pk=sub.pk).exists())


class SaveDeletePushSubscriptionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")

    def test_save_creates_subscription(self):
        save_push_subscription(self.user, "https://push.example/1", "p", "a")
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 1)

    def test_save_is_idempotent_per_endpoint(self):
        save_push_subscription(self.user, "https://push.example/1", "p1", "a1")
        save_push_subscription(self.user, "https://push.example/1", "p2", "a2")
        subs = PushSubscription.objects.filter(user=self.user)
        self.assertEqual(subs.count(), 1)
        self.assertEqual(subs.first().p256dh, "p2")

    def test_delete_removes_subscription(self):
        save_push_subscription(self.user, "https://push.example/1", "p", "a")
        delete_push_subscription(self.user, "https://push.example/1")
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 0)


class TutorPushEndpointsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.client = Client()

    def test_subscribe_requires_login(self):
        response = self.client.post(
            "/push/subscribe/",
            data=json.dumps(
                {"endpoint": "https://push.example/1", "keys": {"p256dh": "p", "auth": "a"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)  # redirect to login

    def test_subscribe_creates_subscription(self):
        self.client.login(username="tutor", password="pass")
        response = self.client.post(
            "/push/subscribe/",
            data=json.dumps(
                {"endpoint": "https://push.example/1", "keys": {"p256dh": "p", "auth": "a"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(user=self.user).exists())

    def test_subscribe_rejects_bad_payload(self):
        self.client.login(username="tutor", password="pass")
        response = self.client.post(
            "/push/subscribe/", data=json.dumps({"nonsense": True}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_unsubscribe_removes_subscription(self):
        self.client.login(username="tutor", password="pass")
        PushSubscription.objects.create(
            user=self.user, endpoint="https://push.example/1", p256dh="p", auth="a"
        )
        response = self.client.post(
            "/push/unsubscribe/",
            data=json.dumps({"endpoint": "https://push.example/1"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(user=self.user).exists())


class TutorSettingsNotificationFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.client = Client()
        self.client.login(username="tutor", password="pass")

    def test_settings_page_shows_notification_checkboxes(self):
        response = self.client.get("/settings/")
        self.assertContains(response, "notify_portal_booking_email")
        self.assertContains(response, "notify_portal_booking_push")

    def test_saving_notification_preferences_persists(self):
        response = self.client.post(
            "/settings/",
            {
                "save_notifications": "1",
                "notify_portal_booking_email": "on",
                # push left unchecked
            },
        )
        self.assertEqual(response.status_code, 302)
        pref = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(pref.notify_portal_booking_email)
        self.assertFalse(pref.notify_portal_booking_push)


class SettingsPagePushStateIsClientSideTest(TestCase):
    """Regression: whether push is "enabled" must be determined by the
    browser (Notification.permission + an active PushManager subscription
    on the current device), never by "does this user have any
    PushSubscription row at all" server-side. A user with a subscription
    from a different/old device must still see the enable button on a
    fresh device instead of a false "already enabled" message - the old
    server-side check hid the button and silently blocked the OS
    permission prompt from ever being shown."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor2", password="pass")
        self.client = Client()
        self.client.login(username="tutor2", password="pass")

    def test_settings_page_renders_both_states_hidden_regardless_of_other_device_subscription(self):
        PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.com/other-device",
            p256dh="p256dh-key",
            auth="auth-key",
        )
        response = self.client.get("/settings/")
        # Both elements are always rendered, hidden by default; only the
        # client's JS (checking this browser's actual subscription state)
        # decides which one to reveal - the server must never claim
        # "already enabled" based on another device's row.
        self.assertContains(response, 'id="pushEnabledText" style="display: none;')
        self.assertContains(response, 'id="pushSubscribeBtn" style="display: none;')
        self.assertNotContains(response, "has_push_subscription")
