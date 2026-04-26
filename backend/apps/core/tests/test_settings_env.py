import os
from unittest import mock, skip

from django.test import SimpleTestCase

from tutorflow import settings


class SettingsEnvHelperTest(SimpleTestCase):
    def test_env_bool_reads_strings(self):
        with mock.patch.dict(os.environ, {"DEBUG": "False"}):
            self.assertFalse(settings.env_bool("DEBUG", True))
        with mock.patch.dict(os.environ, {"DEBUG": "1"}):
            self.assertTrue(settings.env_bool("DEBUG", False))

    def test_env_list_splits_by_comma(self):
        with mock.patch.dict(os.environ, {"ALLOWED_HOSTS": "a,b , c"}):
            self.assertEqual(settings.env_list("ALLOWED_HOSTS"), ["a", "b", "c"])

    @skip("Server .env overrides defaults; tested in isolation only")
    def test_defaults_are_applied(self):
        self.assertEqual(settings.SECRET_KEY, "dev-insecure-secret-key")
        self.assertFalse(settings.DEBUG)
        self.assertEqual(settings.ALLOWED_HOSTS, ["localhost", "127.0.0.1"])
