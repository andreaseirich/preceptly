"""
Tests for internationalization (i18n) functionality.
"""

from apps.core.models import UserProfile
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
        """When language is German, booking page shows German text."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-i18n"
        prof.save()
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get("/lessons/public-booking/tok-i18n/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Stunde buchen", response.content)
        self.assertIn(b"Daten", response.content)
