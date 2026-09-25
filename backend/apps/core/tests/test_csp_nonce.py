"""Skripte nur mit Nonce — und keine Inline-Handler mehr in den Vorlagen.

Die Wächter-Tests durchsuchen alle Vorlagen. Sie schlagen an, sobald wieder ein
onclick="…", ein javascript:-Link oder ein <script> ohne Nonce auftaucht — beides
würde unter der scharfen Richtlinie still blockiert.
"""

import re
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.core.csp import policy_value
from apps.lessons.models import Session, SessionDocument
from apps.meeting.models import MeetingRoom

BACKEND = Path(settings.BASE_DIR)
TEMPLATE_ROOTS = [BACKEND / "apps", BACKEND / "templates"]
HEADER = "Content-Security-Policy-Report-Only"

# Seiten, die actions.js selbst einbinden; alle anderen erben es von hier.
ENTRY_TEMPLATES = {
    "core/base.html",
    "portal/base.html",
    "meeting/room.html",
    "core/ratelimited.html",
}


def _templates():
    for root in TEMPLATE_ROOTS:
        yield from root.rglob("*.html")


def _script_nonce(policy):
    match = re.search(r"'nonce-([^']+)'", policy)
    return match.group(1) if match else None


class NonceHeaderTest(TestCase):
    def test_page_scripts_carry_the_nonce_from_the_header(self):
        response = self.client.get(reverse("core:login"))

        nonce = _script_nonce(response[HEADER])
        self.assertTrue(nonce)
        body = response.content.decode()
        scripts = re.findall(r"<script\b[^>]*>", body, re.IGNORECASE)
        self.assertTrue(scripts)
        for tag in scripts:
            with self.subTest(tag=tag[:80]):
                self.assertIn(f'nonce="{nonce}"', tag)

    def test_nonce_changes_with_every_response(self):
        first = _script_nonce(self.client.get(reverse("core:login"))[HEADER])
        second = _script_nonce(self.client.get(reverse("core:login"))[HEADER])

        self.assertNotEqual(first, second)

    def test_strict_dynamic_only_together_with_a_nonce(self):
        # Ohne Nonce würde 'strict-dynamic' jedes Skript sperren.
        self.assertNotIn("'strict-dynamic'", policy_value())
        self.assertIn("'nonce-abc' 'strict-dynamic'", policy_value("abc"))


class TemplateGuardTest(TestCase):
    """Wächter über alle Vorlagen."""

    def test_no_inline_event_handlers(self):
        found = []
        for path in _templates():
            text = path.read_text(encoding="utf-8")
            for m in re.finditer(r"""\son[a-z]+\s*=\s*["']""", text, re.IGNORECASE):
                found.append(f"{path.relative_to(BACKEND)}: {m.group(0).strip()}")
        self.assertEqual(
            found, [], "Inline-Handler gefunden - stattdessen data-click usw. (actions.js)"
        )

    def test_no_javascript_urls(self):
        found = [
            str(p.relative_to(BACKEND))
            for p in _templates()
            if re.search(
                r"""href\s*=\s*["']\s*javascript:""", p.read_text(encoding="utf-8"), re.IGNORECASE
            )
        ]
        self.assertEqual(found, [])

    def test_every_script_tag_has_the_nonce(self):
        missing = []
        for path in _templates():
            text = path.read_text(encoding="utf-8")
            for tag in re.findall(r"<script\b[^>]*>", text, re.IGNORECASE):
                if 'nonce="{{ csp_nonce }}"' not in tag:
                    missing.append(f"{path.relative_to(BACKEND)}: {tag}")
        self.assertEqual(missing, [])

    def test_templates_with_data_actions_load_actions_js(self):
        """Wer data-click & Co. nutzt, muss actions.js haben - selbst oder über die Basis."""
        uncovered = []
        attr = re.compile(
            r"data-(click|change|mouseover|mouseout|confirm|href|history-back|autosubmit)\b"
        )
        for path in _templates():
            text = path.read_text(encoding="utf-8")
            if not attr.search(text):
                continue
            name = "/".join(path.parts[-2:])
            if name in ENTRY_TEMPLATES:
                self.assertIn("js/actions.js", text, name)
                continue
            parent = re.search(r"""\{%\s*extends\s+["']([^"']+)["']""", text)
            is_partial = path.name.startswith("_") or "partials" in path.parts
            if not is_partial and (not parent or parent.group(1) not in ENTRY_TEMPLATES):
                uncovered.append(name)
        self.assertEqual(uncovered, [])

    def test_actions_js_is_a_static_file(self):
        self.assertIsNotNone(finders.find("js/actions.js"))


class MeetingRoomDocumentNameTest(TestCase):
    """Ein Dokumentname darf nie als JavaScript-Quelltext in der Seite landen."""

    def test_document_name_is_data_not_code(self):
        tutor = User.objects.create_user(username="tutor", password="pass")
        contract = Contract.objects.create(
            user=tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
        )
        lesson = Session.objects.create(
            contract=contract, date=date.today(), start_time=time(15, 0), duration_minutes=60
        )
        room = MeetingRoom.objects.create(lesson=lesson, is_active=True)
        evil = "x');alert(1);//"
        SessionDocument.objects.create(
            session=lesson,
            file=SimpleUploadedFile(
                "blatt.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf"
            ),
            name=evil,
        )
        self.client.force_login(tutor)

        body = self.client.get(
            reverse("meeting:room", kwargs={"token": room.token})
        ).content.decode()

        self.assertIn('data-click="openDocFromButton"', body)
        self.assertIn('data-doc-name="x&#x27;);alert(1);//"', body)
        self.assertNotIn(evil, body)
        self.assertNotIn("openDocAsBackground('", body)
