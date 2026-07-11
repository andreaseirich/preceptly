"""Tests for magic-byte upload validation in lessons and portal upload paths."""

import io

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TestCase

from apps.lessons.forms import SessionDocumentForm


def _make_upload(content: bytes, filename: str, content_type: str = "application/octet-stream"):
    buf = io.BytesIO(content)
    return InMemoryUploadedFile(buf, "file", filename, content_type, len(content), None)


class SessionDocumentFormMagicByteTest(TestCase):
    """clean_file must reject files whose magic bytes don't match the extension."""

    def _form(self, upload):
        return SessionDocumentForm(
            data={"name": "test"},
            files={"file": upload},
        )

    def test_valid_pdf_accepted(self):
        upload = _make_upload(b"%PDF-1.4 dummy content", "report.pdf", "application/pdf")
        form = self._form(upload)
        self.assertTrue(form.is_valid(), form.errors)

    def test_pdf_extension_with_wrong_magic_rejected(self):
        """A file with .pdf extension but no PDF magic bytes must be rejected."""
        upload = _make_upload(b"FAKECONTENT not a pdf", "evil.pdf", "application/pdf")
        form = self._form(upload)
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)

    def test_valid_png_accepted(self):
        png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        upload = _make_upload(png_magic, "image.png", "image/png")
        form = self._form(upload)
        self.assertTrue(form.is_valid(), form.errors)

    def test_png_extension_with_wrong_magic_rejected(self):
        upload = _make_upload(b"NOTAPNG content here", "image.png", "image/png")
        form = self._form(upload)
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)
