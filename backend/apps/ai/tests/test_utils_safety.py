from django.test import SimpleTestCase

from apps.ai.utils_safety import REDACTED, sanitize_context


class SanitizeContextTest(SimpleTestCase):
    """Tests für den PII-Sanitizer."""

    def test_sanitize_context_removes_pii(self):
        ctx = {
            "student": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "subjects": "Math",
                "notes": "Needs focus",
            },
            "lesson": {"notes": "harmless"},
            "list": [{"phone": "12345", "notes": "ok"}],
        }

        sanitized = sanitize_context(ctx)

        self.assertEqual(sanitized["student"]["full_name"], REDACTED)
        self.assertEqual(sanitized["student"]["email"], REDACTED)
        self.assertEqual(sanitized["student"]["subjects"], "Math")
        self.assertEqual(sanitized["list"][0]["phone"], REDACTED)

    def test_sanitize_masks_email_and_phone_in_free_text(self):
        ctx = {
            "notes": "Reach me at john.doe@test.org or +49 151 2345678 for details.",
            "nested": ["Call +1-202-555-0199 tomorrow."],
        }

        sanitized = sanitize_context(ctx)

        self.assertNotIn("john.doe@test.org", sanitized["notes"])
        self.assertNotIn("151 2345678", sanitized["notes"])
        self.assertEqual(sanitized["notes"].count(REDACTED) >= 1, True)
        self.assertIn(REDACTED, sanitized["nested"][0])
