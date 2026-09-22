from pathlib import Path

from django.test import SimpleTestCase

ROOM_TEMPLATE = Path(__file__).resolve().parent / "templates" / "meeting" / "room.html"


class PdfJsHardeningTest(SimpleTestCase):
    """PDFs in the meeting room can be uploaded by portal users. pdf.js
    < 4.2.67 runs attacker-controlled font code unless eval is disabled
    (CVE-2024-4367), so every getDocument() call has to pass
    isEvalSupported: false."""

    def test_every_get_document_call_disables_eval(self):
        source = ROOM_TEMPLATE.read_text(encoding="utf-8")
        calls = source.count("pdfjsLib.getDocument(")
        self.assertGreater(calls, 0)
        self.assertEqual(source.count("isEvalSupported: false"), calls)
