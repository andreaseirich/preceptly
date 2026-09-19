from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import UserProfile


class SettingsPageLayoutTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_sp", password="pass")
        self.client.force_login(self.user)
        self.url = reverse("core:settings")

    def test_settings_are_grouped_into_four_sections(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for panel_id in (
            "settings-account",
            "settings-scheduling",
            "settings-billing",
            "settings-notifications",
        ):
            self.assertContains(response, f'id="{panel_id}"')

    def test_anchors_other_pages_link_to_still_exist(self):
        # dashboard -> #id_email, calendar sync -> #calendar-sync,
        # invoice detail -> #billing, invoice create -> #institutes
        response = self.client.get(self.url)
        for anchor in ("id_email", "calendar-sync", "billing", "institutes"):
            self.assertContains(response, f'id="{anchor}"')

    def test_working_hours_rendered_for_every_weekday(self):
        response = self.client.get(self.url)
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            for suffix in ("enabled", "start", "end"):
                self.assertContains(response, f'id="id_{day}_{suffix}"')

    def test_section_param_selects_initial_tab(self):
        response = self.client.get(self.url + "?section=billing")
        self.assertContains(response, 'data-initial-section="billing"')


class PortalBufferHintSettingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor_ph", password="pass")
        self.client.force_login(self.user)
        self.url = reverse("core:settings")

    def _enabled(self):
        return UserProfile.objects.get(user=self.user).portal_buffer_hint_enabled

    def test_enabled_by_default(self):
        profile, _created = UserProfile.objects.get_or_create(user=self.user)
        self.assertTrue(profile.portal_buffer_hint_enabled)

    def test_unchecking_turns_hint_off_and_returns_to_section(self):
        response = self.client.post(self.url, {"save_portal": "1"})
        self.assertRedirects(response, f"{self.url}?section=portal", fetch_redirect_response=False)
        self.assertFalse(self._enabled())

    def test_checking_turns_hint_back_on(self):
        UserProfile.objects.update_or_create(
            user=self.user, defaults={"portal_buffer_hint_enabled": False}
        )
        self.client.post(self.url, {"save_portal": "1", "portal_buffer_hint_enabled": "on"})
        self.assertTrue(self._enabled())


class SettingsSaveRedirectTest(TestCase):
    """Saving any card returns to the tab it lives in (via ?section=, not a
    #fragment, so the success message at the top of the page stays visible)."""

    def setUp(self):
        self.user = User.objects.create_user(username="tutor_sr", password="pass")
        self.client.force_login(self.user)
        self.url = reverse("core:settings")

    def test_timezone(self):
        response = self.client.post(self.url, {"save_timezone": "1", "timezone": "Europe/Berlin"})
        self.assertRedirects(
            response, f"{self.url}?section=timezone", fetch_redirect_response=False
        )

    def test_notifications(self):
        response = self.client.post(self.url, {"save_notifications": "1"})
        self.assertRedirects(
            response, f"{self.url}?section=notifications", fetch_redirect_response=False
        )

    def test_billing(self):
        response = self.client.post(
            self.url,
            {"save_billing_profile": "1", "billing_name": "Max", "billing_address": "Weg 1"},
        )
        self.assertRedirects(response, f"{self.url}?section=billing", fetch_redirect_response=False)

    def test_working_hours(self):
        response = self.client.post(
            self.url, {"monday_enabled": "on", "monday_start": "09:00", "monday_end": "17:00"}
        )
        self.assertRedirects(
            response, f"{self.url}?section=working-hours", fetch_redirect_response=False
        )
