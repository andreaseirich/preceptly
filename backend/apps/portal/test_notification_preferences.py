"""
Tests for the portal side of push notification preferences: gating in
send_booking_notification_portal/send_login_reminder, the portal push
subscribe/unsubscribe endpoints, and the profile "notifications" form.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.core.models import NotificationPreference, PushSubscription
from apps.portal.email_service import send_booking_notification_portal, send_login_reminder
from apps.portal.models import ParentStudentLink, PortalUser

User = get_user_model()


def _make_tutor(username="tutor1"):
    return User.objects.create_user(
        username=username, password="pw_tutor", email=f"{username}@example.com"
    )


def _make_portal_user(tutor, role, username="portaluser1", password="pw_portal"):
    user = User.objects.create_user(
        username=username, password=password, email=f"{username}@example.com"
    )
    return PortalUser.objects.create(user=user, role=role, tutor=tutor)


def _make_contract(tutor):
    from datetime import date
    from decimal import Decimal

    from apps.contracts.models import Contract

    return Contract.objects.create(
        user=tutor,
        first_name="Test",
        last_name="Student",
        hourly_rate=Decimal("30.00"),
        start_date=date(2025, 1, 1),
    )


def _make_session(contract, tutor, date_, start_time):
    from apps.lessons.models import Lesson

    return Lesson.objects.create(
        contract=contract, date=date_, start_time=start_time, duration_minutes=60
    )


class SendBookingNotificationPortalTest(TestCase):
    def setUp(self):
        self.tutor = _make_tutor()
        self.contract = _make_contract(self.tutor)

    def test_email_sent_by_default_no_preference_row(self):
        from datetime import date, time

        session = _make_session(self.contract, self.tutor, date(2025, 6, 2), time(10, 0))
        send_booking_notification_portal(session, self.tutor)
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)

    def test_email_skipped_when_preference_disabled(self):
        from datetime import date, time

        NotificationPreference.objects.create(user=self.tutor, notify_portal_booking_email=False)
        session = _make_session(self.contract, self.tutor, date(2025, 6, 3), time(10, 0))
        send_booking_notification_portal(session, self.tutor)
        from django.core import mail

        self.assertEqual(len(mail.outbox), 0)

    @override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_ADMIN_EMAIL="a@b.de")
    def test_push_attempted_when_subscribed(self):
        from datetime import date, time

        PushSubscription.objects.create(
            user=self.tutor, endpoint="https://push.example/1", p256dh="k", auth="a"
        )
        session = _make_session(self.contract, self.tutor, date(2025, 6, 4), time(10, 0))
        with patch("apps.core.push_service.webpush") as mock_webpush:
            send_booking_notification_portal(session, self.tutor)
        mock_webpush.assert_called_once()


class SendLoginReminderTest(TestCase):
    def setUp(self):
        self.tutor = _make_tutor()
        self.parent_pu = _make_portal_user(self.tutor, "parent")
        self.contract = _make_contract(self.tutor)
        ParentStudentLink.objects.create(
            parent=self.parent_pu, contract=self.contract, is_active=True
        )

    def test_backward_compatible_without_recipient_user_always_emails(self):
        send_login_reminder(self.contract, self.parent_pu.user.email, "Tutor Name", role="student")
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)

    def test_email_skipped_when_disabled_via_recipient_user(self):
        NotificationPreference.objects.create(
            user=self.parent_pu.user, notify_login_reminder_email=False
        )
        send_login_reminder(
            self.contract,
            self.parent_pu.user.email,
            "Tutor Name",
            role="student",
            recipient_user=self.parent_pu.user,
        )
        from django.core import mail

        self.assertEqual(len(mail.outbox), 0)

    def test_email_still_sent_when_enabled_via_recipient_user(self):
        send_login_reminder(
            self.contract,
            self.parent_pu.user.email,
            "Tutor Name",
            role="student",
            recipient_user=self.parent_pu.user,
        )
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)


class PortalPushEndpointsTest(TestCase):
    def setUp(self):
        self.tutor = _make_tutor()
        self.portal_user = _make_portal_user(self.tutor, "student")
        self.client = Client()
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

    def test_subscribe_requires_portal_login(self):
        anon_client = Client()
        response = anon_client.post(
            "/portal/push/subscribe/",
            data=json.dumps(
                {"endpoint": "https://push.example/1", "keys": {"p256dh": "p", "auth": "a"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_subscribe_creates_subscription(self):
        response = self.client.post(
            "/portal/push/subscribe/",
            data=json.dumps(
                {"endpoint": "https://push.example/1", "keys": {"p256dh": "p", "auth": "a"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(user=self.portal_user.user).exists())

    def test_unsubscribe_removes_subscription(self):
        PushSubscription.objects.create(
            user=self.portal_user.user, endpoint="https://push.example/1", p256dh="p", auth="a"
        )
        response = self.client.post(
            "/portal/push/unsubscribe/",
            data=json.dumps({"endpoint": "https://push.example/1"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(user=self.portal_user.user).exists())


class PortalProfileNotificationFormTest(TestCase):
    def setUp(self):
        self.tutor = _make_tutor()
        self.portal_user = _make_portal_user(self.tutor, "student")
        self.contract = _make_contract(self.tutor)
        ParentStudentLink.objects.create(
            parent=self.portal_user, contract=self.contract, is_active=True
        )
        self.client = Client()
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

    def test_profile_page_shows_notification_checkboxes(self):
        response = self.client.get("/portal/profile/")
        self.assertContains(response, "notify_login_reminder_email")
        self.assertContains(response, "notify_login_reminder_push")

    def test_saving_notification_preferences_persists(self):
        response = self.client.post(
            "/portal/profile/",
            {
                "action": "notifications",
                "notify_login_reminder_email": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        pref = NotificationPreference.objects.get(user=self.portal_user.user)
        self.assertTrue(pref.notify_login_reminder_email)
        self.assertFalse(pref.notify_login_reminder_push)
