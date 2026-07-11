"""
Shared upload validation helpers for magic-byte checks and filename sanitisation.
Used by meeting, portal, and lessons upload paths.
"""

import os
import unicodedata

from django.utils.text import get_valid_filename

_MAGIC = {
    ".pdf": [(0, b"%PDF")],
    ".jpg": [(0, b"\xff\xd8\xff")],
    ".jpeg": [(0, b"\xff\xd8\xff")],
    ".png": [(0, b"\x89PNG\r\n\x1a\n")],
    ".gif": [(0, b"GIF87a"), (0, b"GIF89a")],
    ".webp": [(0, b"RIFF"), (8, b"WEBP")],
    ".docx": [(0, b"PK\x03\x04")],
    ".doc": [(0, b"\xd0\xcf\x11\xe0")],
    ".xlsx": [(0, b"PK\x03\x04")],
    ".xls": [(0, b"\xd0\xcf\x11\xe0")],
    ".pptx": [(0, b"PK\x03\x04")],
    ".mp3": [(0, b"ID3"), (0, b"\xff\xfb"), (0, b"\xff\xf3"), (0, b"\xff\xf2")],
    ".mp4": [(4, b"ftyp")],
}


def validate_file_magic(file, ext: str) -> bool:
    """Return True if *file* has the expected magic bytes for *ext*."""
    if ext == ".txt":
        chunk = file.read(8192)
        file.seek(0)
        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    checks = _MAGIC.get(ext)
    if not checks:
        return False
    header = file.read(12)
    file.seek(0)
    if ext == ".webp":
        return all(header[offset : offset + len(sig)] == sig for offset, sig in checks)
    return any(header[offset : offset + len(sig)] == sig for offset, sig in checks)


def sanitize_doc_name(raw: str) -> str:
    """Normalise and sanitise a user-supplied document display name."""
    raw = unicodedata.normalize("NFKC", raw)
    raw = os.path.basename(raw)
    raw = get_valid_filename(raw)
    return raw[:200] or "unnamed"
