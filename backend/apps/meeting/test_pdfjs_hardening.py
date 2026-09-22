from pathlib import Path

from django.test import SimpleTestCase

MEETING_APP = Path(__file__).resolve().parent
ROOM_TEMPLATE = MEETING_APP / "templates" / "meeting" / "room.html"
PDFJS_DIR = MEETING_APP.parent / "core" / "static" / "js" / "pdfjs"


class PdfJsHardeningTest(SimpleTestCase):
    """PDFs in the meeting room can be uploaded by portal users, so the
    viewer must not run code from them: pdf.js is served from our own static
    files (no CDN) and every getDocument() call disables eval."""

    def test_every_get_document_call_disables_eval(self):
        source = ROOM_TEMPLATE.read_text(encoding="utf-8")
        calls = source.count("pdfjsLib.getDocument(")
        self.assertGreater(calls, 0)
        self.assertEqual(source.count("isEvalSupported: false"), calls)

    def test_pdfjs_is_self_hosted(self):
        source = ROOM_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("cdnjs", source)
        self.assertIn("js/pdfjs/pdf.min.mjs", source)
        self.assertIn("js/pdfjs/pdf.worker.min.mjs", source)

    def test_shipped_pdfjs_files_exist_and_are_current(self):
        for name in ("pdf.min.mjs", "pdf.worker.min.mjs"):
            self.assertTrue((PDFJS_DIR / name).is_file(), f"{name} fehlt")
        version = (PDFJS_DIR / "VERSION.txt").read_text(encoding="utf-8").strip()
        major = int(version.split(".")[0])
        # CVE-2024-4367 is fixed as of 4.2.67
        self.assertGreaterEqual(major, 5, f"pdf.js {version} ist zu alt")
