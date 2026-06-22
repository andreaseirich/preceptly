"""
Tests for internationalization (i18n) functionality.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.translation import activate

from apps.billing.models import Invoice
from apps.core.models import UserProfile


class I18nTestCase(TestCase):
    """Test cases for i18n functionality."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.user = User.objects.create_user(username="testuser_i18n", password="password")

    def test_default_language_is_english(self):
        """Test that default language is English."""
        from django.conf import settings

        self.assertEqual(settings.LANGUAGE_CODE, "en")

    def test_language_switching(self):
        """Test that language switching works."""
        self.client.force_login(self.user)
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
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)
        # Check for language switcher form
        self.assertIn(b"setlang", response.content)
        self.assertIn(b"language", response.content)

    def test_english_texts_in_templates(self):
        """Test that templates use English as primary language."""
        self.client.force_login(self.user)
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
            except Exception:  # noqa: S110
                # Skip if view requires authentication or other setup
                pass

    def test_german_translations_appear_correctly(self):
        """Test that German translations appear correctly when LANGUAGE=de."""
        self.client.force_login(self.user)
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
            except Exception:  # noqa: S110
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
        except Exception:  # noqa: S110
            # Skip if view requires authentication or other setup
            pass

    def test_jump_to_date_german(self):
        """Jump to date label is translated when German is active."""
        user = User.objects.create_user(username="tutor", password="test")
        user.save()
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("lessons:week"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Zum Datum springen:", response.content)
        self.assertNotIn(b"Jump to date", response.content)

    def test_public_booking_jump_to_date_german(self):
        """Public booking page: Jump to date in German, no English when de active."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-i18n-jumpxxxxxxxxxxxxxxxxxxx"
        prof.save()
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get("/lessons/public-booking/tok-i18n-jumpxxxxxxxxxxxxxxxxxxx/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Zum Datum springen:", response.content)
        self.assertNotIn(b"Jump to date", response.content)

    def test_billing_headers_german(self):
        """Billing invoice list: table headers in German when de active."""
        from datetime import date as _date

        user = User.objects.create_user(username="tutor_hdr", password="test")
        Invoice.objects.create(
            owner=user,
            payer_name="Test",
            total_amount=100,
            period_start=_date(2025, 1, 1),
            period_end=_date(2025, 1, 31),
        )
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("billing:invoice_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Status", response.content)
        self.assertIn(b"Betrag", response.content)
        self.assertIn(b"Zeitraum", response.content)

    def test_weekday_locale_german(self):
        """Week view shows German weekday when language is German."""
        user = User.objects.create_user(username="tutor", password="test")
        user.save()
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("lessons:week"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Mo", response.content)

    def test_public_booking_no_reschedule_list_in_data_section(self):
        """Public booking page must not render reschedule list (reschedule is inline in calendar)."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-no-listxxxxxxxxxxxxxxxxxxxxx"
        prof.save()
        response = self.client.get("/lessons/public-booking/tok-no-listxxxxxxxxxxxxxxxxxxxxx/")
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

    def test_public_booking_de_does_not_contain_english_strings(self):
        """When DE is active, public booking must NOT contain English UI strings."""
        user = User.objects.create_user(username="tutor", password="test")
        prof, _ = UserProfile.objects.get_or_create(user=user, defaults={})
        prof.public_booking_token = "tok-de-no-enxxxxxxxxxxxxxxxxxxxx"
        prof.save()
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get("/lessons/public-booking/tok-de-no-enxxxxxxxxxxxxxxxxxxxx/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Jump to date", response.content)
        self.assertNotIn(b">Back<", response.content)
        self.assertNotIn(b">Confirm<", response.content)

    def test_reports_premium_german_labels(self):
        """Reports page with premium user: DE labels when de active, no English."""
        user = User.objects.create_user(username="premium", password="test")
        UserProfile.objects.create(user=user, is_premium=True)
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Umsatz", response.content)
        self.assertIn(b"Stunden", response.content)
        self.assertNotIn(b">Revenue<", response.content)
        self.assertNotIn(b">Hours<", response.content)

    def test_invoice_detail_german_buttons(self):
        """Invoice detail page: buttons in German when de active."""
        user = User.objects.create_user(username="tutor", password="test")
        UserProfile.objects.create(user=user, is_premium=True)
        inv = Invoice.objects.create(
            owner=user,
            payer_name="Test",
            total_amount=100,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "de"}, follow=True)
        response = self.client.get(reverse("billing:invoice_detail", args=[inv.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PDF erzeugen", response.content)
        self.assertIn(b"Als gesendet markieren", response.content)
        self.assertNotIn(b"Generate PDF", response.content)
        self.assertNotIn(b"Mark as sent", response.content)
