"""
Tests for PDF text extraction used as extra AI context.
"""

import io
from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from reportlab.pdfgen import canvas

from apps.ai.pdf_extract import (
    MAX_PDF_SIZE_BYTES,
    PdfExtractionError,
    extract_pdf_text,
)


def _make_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, text)
    c.save()
    return buffer.getvalue()


class ExtractPdfTextTest(SimpleTestCase):
    def test_extracts_text_from_a_real_pdf(self):
        pdf_bytes = _make_pdf("Aufgabe 1: Löse die Gleichung 2x + 3 = 7")
        upload = SimpleUploadedFile("worksheet.pdf", pdf_bytes, content_type="application/pdf")

        result = extract_pdf_text(upload)

        self.assertIn("Aufgabe 1", result)

    def test_oversized_pdf_is_rejected(self):
        upload = Mock()
        upload.size = MAX_PDF_SIZE_BYTES + 1

        with self.assertRaises(PdfExtractionError):
            extract_pdf_text(upload)

    def test_corrupt_file_is_rejected_with_a_clear_error(self):
        upload = SimpleUploadedFile(
            "not-a-pdf.pdf", b"this is not a pdf file", content_type="application/pdf"
        )

        with self.assertRaises(PdfExtractionError):
            extract_pdf_text(upload)

    def test_extracted_text_is_capped(self):
        pdf_bytes = _make_pdf("A" * 100)
        upload = SimpleUploadedFile("worksheet.pdf", pdf_bytes, content_type="application/pdf")

        result = extract_pdf_text(upload)

        self.assertLessEqual(len(result), 2000)
