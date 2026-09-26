"""
Tests for registration flow and premium default.
"""

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.core.models import UserProfile


class RegisterViewTest(TestCase):
    """Tests for registration."""

    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_register_creates_user_and_profile(self):
        """Registration creates User and UserProfile with subscription_tier="free"."""
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "newtutor",
                "email": "newtutor@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="newtutor")
        self.assertTrue(user.check_password("SecurePass123!"))
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.subscription_tier, "free")

    def test_register_redirects_authenticated_user(self):
        """Authenticated user visiting /register/ is redirected to dashboard."""
        User.objects.create_user(username="existing", password="test")
        self.client.login(username="existing", password="test")
        response = self.client.get(reverse("core:register"))
        self.assertRedirects(response, reverse("core:dashboard"))

    def test_duplicate_username_generic_error(self):
        """Duplicate username shows generic error, no enumeration."""
        User.objects.create_user(username="taken", password="test")
        response = self.client.post(
            reverse("core:register"),
            {"username": "taken", "password1": "SecurePass123!", "password2": "SecurePass123!"},
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertTrue(
            "Registration failed" in content
            or "Please try" in content
            or "different username" in content,
            msg="Should show generic error, not 'username exists'",
        )
        self.assertEqual(User.objects.filter(username="taken").count(), 1)

    def test_register_with_email_saves_it(self):
        """The email given at registration is saved to the user."""
        self.client.post(
            reverse("core:register"),
            {
                "username": "withemail",
                "email": "withemail@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        user = User.objects.get(username="withemail")
        self.assertEqual(user.email, "withemail@example.com")

    def test_register_without_email_is_rejected(self):
        """Ohne E-Mail keine Registrierung - sonst ist ein vergessenes Passwort
        nicht zu retten und der Tutor nicht erreichbar."""
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "noemailreg",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
                "avv_consent": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="noemailreg").exists())

    def test_email_field_is_marked_required(self):
        response = self.client.get(reverse("core:register"))
        self.assertContains(response, 'id="id_email" required aria-required="true"')

    def test_login_after_register(self):
        """After registration, user is logged in and can access dashboard."""
        response = self.client.post(
            reverse("core:register"),
            {
                "username": "fresh",
                "email": "fresh@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)


class PremiumGuardTest(TestCase):
    """Tests that non-premium users cannot access premium features."""

    def setUp(self):
        self.client = Client()
        self.non_premium = User.objects.create_user(username="np", password="test")
        UserProfile.objects.create(user=self.non_premium)

    def test_non_premium_cannot_generate_lesson_plan(self):
        """Non-premium user gets redirect + error when POSTing to generate lesson plan."""
        from datetime import date, time

        from apps.contracts.models import Contract
        from apps.lessons.models import Session

        contract = Contract.objects.create(
            user=self.non_premium,
            first_name="A",
            last_name="B",
            hourly_rate=30,
            unit_duration_minutes=60,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            is_active=True,
        )
        session = Session.objects.create(
            contract=contract,
            date=date(2025, 3, 1),
            start_time=time(10, 0),
            duration_minutes=60,
            status="taught",
        )
        self.client.login(username="np", password="test")
        response = self.client.post(
            reverse("ai:generate_lesson_plan", kwargs={"lesson_id": session.pk}),
            data={},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "premium")


@override_settings(ADMIN_NOTIFICATION_EMAIL="admin@preceptly.de")
class RegistrationAdminNotificationTest(TestCase):
    """Tests for the HTML admin notification email sent on new registration."""

    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_notification_sent_with_html_alternative(self):
        """Registering sends an HTML+plain admin notification email."""
        self.client.post(
            reverse("core:register"),
            {
                "username": "mailtest",
                "email": "mailtest@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        admin_mails = [m for m in mail.outbox if m.to == ["admin@preceptly.de"]]
        self.assertEqual(len(admin_mails), 1)
        msg = admin_mails[0]
        self.assertIn("mailtest", msg.subject)
        self.assertTrue(msg.alternatives, "Expected an HTML alternative to be attached")
        html_body = msg.alternatives[0][0]
        self.assertEqual(msg.alternatives[0][1], "text/html")
        self.assertNotIn("(keine Angabe)", html_body)

    def test_notification_names_username_and_email(self):
        self.client.post(
            reverse("core:register"),
            {
                "username": "mailtest3",
                "email": "mailtest3@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        msg = next(m for m in mail.outbox if m.to == ["admin@preceptly.de"])
        html_body = msg.alternatives[0][0]
        for body in (msg.body, html_body):
            self.assertIn("mailtest3", body)
            self.assertIn("mailtest3@example.com", body)
            self.assertNotIn("Account-Typ", body)
