"""
Text extraction for tutor-supplied PDF material (e.g. worksheets, past
exams) used as extra context for lesson plan generation.
"""

import logging

from django.utils.translation import gettext_lazy as _
from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

MAX_PDF_SIZE_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 15
MAX_EXTRACTED_CHARS = 2000


class PdfExtractionError(Exception):
    """Raised when an uploaded PDF cannot be used as AI context."""

    pass


def extract_pdf_text(uploaded_file) -> str:
    """
    Extracts plain text from the first MAX_PDF_PAGES pages of an uploaded
    PDF, capped at MAX_EXTRACTED_CHARS. Never raises for a page that fails
    to extract (e.g. scanned image page with no text layer) - only for
    conditions that make the whole file unusable.
    """
    if uploaded_file.size > MAX_PDF_SIZE_BYTES:
        raise PdfExtractionError(_("The PDF is too large (maximum 5 MB)."))

    try:
        reader = PdfReader(uploaded_file)
    except (PdfReadError, ValueError) as e:
        raise PdfExtractionError(_("The PDF could not be read.")) from e

    if reader.is_encrypted:
        raise PdfExtractionError(_("Password-protected PDFs are not supported."))

    parts = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        try:
            parts.append(page.extract_text() or "")
        except Exception as e:
            logger.warning("Could not extract text from a PDF page: %s", e)
            continue

    return "\n".join(parts).strip()[:MAX_EXTRACTED_CHARS]
