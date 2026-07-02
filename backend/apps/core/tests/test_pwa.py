from django.contrib.auth.models import User
from django.test import TestCase


class ManifestViewTest(TestCase):
    def test_manifest_returns_200_with_correct_content_type(self):
        response = self.client.get("/manifest.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response.get("Content-Type", ""))

    def test_manifest_contains_name(self):
        response = self.client.get("/manifest.json")
        self.assertIn(b"Preceptly", response.content)

    def test_service_worker_returns_200(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.get("Content-Type", ""))


class SettingsInstallHintTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="pass")
        self.client.login(username="tutor", password="pass")

    def test_settings_page_contains_install_button(self):
        response = self.client.get("/settings/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="pwaSettingsInstallBtn"')

    def test_settings_page_contains_install_section(self):
        response = self.client.get("/settings/")
        self.assertContains(response, "pwa-install-section")
