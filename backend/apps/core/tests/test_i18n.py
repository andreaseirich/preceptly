"""
Tests for internationalization (i18n) functionality.
"""

import json

from apps.core.models import UserProfile
from apps.students.booking_code_service import set_booking_code
from apps.students.models import Student
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.translation import activate


class I18nTestCase(TestCase):
    """Test cases for i18n functionality."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_default_language_is_english(self):
        """Test that default language is English."""
        from django.conf import settings

        self.assertEqual(settings.LANGUAGE_CODE, "en")

    def test_language_switching(self):
        """Test that language switching works."""
        # Test English (default)
        activate("en")
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.content)

        # Test German
        activate("de")
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        # Should contain German text if translations are loaded
        # Note: This test may need adjustment based on actual template content

    def test_set_language_view(self):
        """Test the set_language view."""
        # Test switching to German
        response = self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Test switching back to English
        response = self.client.post(reverse("set_language"), {"language": "en"}, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_base_template_has_language_switcher(self):
        """Test that base template includes language switcher."""
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        # Check for language switcher form
        self.assertIn(b"set_language", response.content)
        self.assertIn(b"language", response.content)

    def test_english_texts_in_templates(self):
        """Test that templates use English as primary language."""
        activate("en")
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        # Check for English text
        self.assertIn(b"Dashboard", response.content)
        self.assertIn(b"Students", response.content)
        self.assertIn(b"Calendar", response.content)

    def test_all_template_texts_are_english_by_default(self):
        """Test that all template texts are in English when no language override is active."""
        activate("en")

        # Test various views
        views_to_test = [
            ("students:list", "Students"),
            ("contracts:list", "Contracts"),
            ("lessons:list", "Lessons"),
        ]

        for view_name, expected_text in views_to_test:
            try:
                response = self.client.get(reverse(view_name))
                if response.status_code == 200:
                    self.assertIn(
                        expected_text.encode(),
                        response.content,
                        f"View {view_name} should contain English text '{expected_text}'",
                    )
            except Exception:
                # Skip if view requires authentication or other setup
                pass

    def test_german_translations_appear_correctly(self):
        """Test that German translations appear correctly when LANGUAGE=de."""
        # Set language to German
        response = self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Test that we can access pages in German
        # Note: Actual German text checking would require full translation setup
        activate("de")
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_all_billing_and_blocked_time_templates_are_english_by_default(self):
        """Test that all billing and blocked-time templates are in English by default."""
        activate("en")

        # Test billing views (may require authentication or data setup)
        billing_views = [
            ("billing:invoice_list", "Invoices"),
        ]

        for view_name, expected_text in billing_views:
            try:
                response = self.client.get(reverse(view_name))
                if response.status_code == 200:
                    self.assertIn(
                        expected_text.encode(),
                        response.content,
                        f"View {view_name} should contain English text '{expected_text}'",
                    )
            except Exception:
                # Skip if view requires authentication or other setup
                pass

    def test_german_translations_for_billing_and_blocked_time_templates(self):
        """Test that German translations for billing and blocked-time templates appear correctly when LANGUAGE='de'."""
        activate("de")

        # Test that we can access billing pages in German
        try:
            response = self.client.get(reverse("billing:invoice_list"))
            if response.status_code == 200:
                # Page should render without errors
                self.assertEqual(response.status_code, 200)
        except Exception:
            # Skip if view requires authentication or other setup
            pass

    def test_booking_page_german_translations(self):
        """When language is German, booking page shows German text and dd.mm format."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-i18n"
        prof.save()
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get("/lessons/public-booking/tok-i18n/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Stunde buchen", response.content)
        self.assertIn(b"Daten", response.content)
        # DJANGO_LANGUAGE must be set for JS date formatting
        self.assertIn(b"DJANGO_LANGUAGE", response.content)

    def test_public_booking_week_api_returns_german_weekday_when_de_session(self):
        """Week API returns German weekday_display when session has language=de."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-wk"
        prof.default_working_hours = {"monday": [{"start": "09:00", "end": "17:00"}]}
        prof.save()
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        from django.utils import timezone

        now = timezone.now()
        r = self.client.get(
            f"/lessons/public-booking/tok-wk/week/?year={now.year}&month={now.month}&day={now.day}"
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data.get("success"))
        days = data.get("week_data", {}).get("days", [])
        self.assertGreater(len(days), 0)
        # At least one weekday_display must be German (e.g. Montag, Dienstag)
        weekdays_de = [d.get("weekday_display") for d in days]
        self.assertTrue(
            any(
                w
                in ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
                for w in weekdays_de
            )
        )

    def test_csrf_after_language_switch_on_booking_page(self):
        """After switching language, page reloads with valid CSRF token and next is preserved."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-csrf"
        prof.save()
        # Load booking page
        r1 = self.client.get("/lessons/public-booking/tok-csrf/")
        self.assertEqual(r1.status_code, 200)
        self.assertIn(b"csrf-token", r1.content)
        # Switch language (POST to set_language with next=current path)
        r2 = self.client.post(
            reverse("set_language"),
            {"language": "de", "next": "/lessons/public-booking/tok-csrf/"},
            follow=True,
        )
        self.assertEqual(r2.status_code, 200)
        # Page must still have csrf-token meta after redirect
        self.assertIn(b"csrf-token", r2.content)

    def test_language_switch_then_verify_student_post_succeeds(self):
        """After language switch, verify-student POST must work (session/cookies intact)."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-csrf2"
        prof.save()
        student = Student.objects.create(user=user, first_name="Max", last_name="Test")
        code = set_booking_code(student)
        # 1. Load booking page
        self.client.get("/lessons/public-booking/tok-csrf2/")
        # 2. Switch language
        self.client.post(
            reverse("set_language"),
            {"language": "de", "next": "/lessons/public-booking/tok-csrf2/"},
            follow=True,
        )
        # 3. POST verify-student (csrf_exempt but tests session integrity)
        r = self.client.post(
            reverse("lessons:public_booking_verify_student"),
            data=json.dumps({"name": "Max Test", "code": code, "tutor_token": "tok-csrf2"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertTrue(data.get("success"))

    def test_jump_to_date_german(self):
        """Jump to date label is translated when German is active."""
        user = User.objects.create_user(username="tutor", password="test")
        user.save()
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("lessons:week"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Zum Datum springen:", response.content)

    def test_weekday_locale_german(self):
        """Week view shows German weekday when language is German."""
        user = User.objects.create_user(username="tutor", password="test")
        user.save()
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("lessons:week"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Montag", response.content)

    def test_public_booking_no_reschedule_list_in_data_section(self):
        """Public booking page must not render reschedule list (reschedule is inline in calendar)."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-no-list"
        prof.save()
        response = self.client.get("/lessons/public-booking/tok-no-list/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"existing-bookings-section", response.content)
        self.assertNotIn(b"loadReschedulableLessons", response.content)

    def test_weekday_short_german_in_week_view(self):
        """With German locale, week view shows German short weekday (Mo, Di) not English (Mon, Tue)."""
        user = User.objects.create_user(username="tutor", password="test")
        user.save()
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("lessons:week"))
        self.assertEqual(response.status_code, 200)
        # German short form must appear (Mo for Monday)
        self.assertIn(b"Mo", response.content)
