"""Rechtstexte nennen Speicherort und Frist der Backups - der AVV sagt Tutoren
tägliche Datensicherungen zu, Hetzner ist dafür Unterauftragsverarbeiter."""

from django.test import TestCase
from django.urls import reverse


class BackupDisclosureTest(TestCase):
    def test_privacy_policy_names_backup_host_and_retention(self):
        body = self.client.get(
            reverse("core:legal_privacy"), HTTP_ACCEPT_LANGUAGE="de"
        ).content.decode()

        self.assertIn("Datensicherung (Hetzner)", body)
        self.assertIn("Hetzner Online GmbH", body)
        self.assertIn("spätestens nach 30 Tagen", body)

    def test_dpa_lists_hetzner_as_subprocessor_in_both_languages(self):
        for lang, basis in (
            ("de", "Keine Drittlandübermittlung"),
            ("en", "No transfer to third countries"),
        ):
            with self.subTest(lang=lang):
                body = self.client.get(
                    reverse("core:legal_avv"), HTTP_ACCEPT_LANGUAGE=lang
                ).content.decode()

                self.assertIn("Hetzner Online GmbH", body)
                self.assertIn(basis, body)
