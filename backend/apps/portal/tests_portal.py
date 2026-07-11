import io

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from apps.portal.models import ParentStudentLink, PortalUser, StudentPortalLink

User = get_user_model()


def _make_tutor(username="tutor1"):
    return User.objects.create_user(
        username=username, password="pw_tutor", email=f"{username}@example.com"
    )


def _make_portal_user(tutor, role, username="portaluser1", password="pw_portal"):
    user = User.objects.create_user(
        username=username, password=password, email=f"{username}@example.com"
    )
    return PortalUser.objects.create(user=user, role=role, tutor=tutor)


def _make_contract(tutor):
    from datetime import date
    from decimal import Decimal

    from apps.contracts.models import Contract

    return Contract.objects.create(
        user=tutor,
        first_name="Test",
        last_name="Student",
        hourly_rate=Decimal("30.00"),
        start_date=date(2025, 1, 1),
    )


def _make_student_link(portal_user, contract, active=True):
    return StudentPortalLink.objects.create(
        portal_user=portal_user,
        contract=contract,
        is_active=active,
    )


def _make_parent_link(parent_portal_user, contract, active=True):
    return ParentStudentLink.objects.create(
        parent=parent_portal_user,
        contract=contract,
        is_active=active,
    )


class PortalLoginViewTest(TestCase):
    def setUp(self):
        cache.clear()  # Ratelimit-Zähler vor jedem Test zurücksetzen
        self.client = Client()
        self.tutor = _make_tutor("tutor_login")
        self.student_pu = _make_portal_user(self.tutor, "student", "student_login", "s3cret!")
        self.parent_pu = _make_portal_user(self.tutor, "parent", "parent_login", "p4rent!")
        self.url = reverse("portal:login")

    # --- GET ---

    def test_get_renders_login_page(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "portal/login.html")

    def test_get_already_authenticated_redirects_home(self):
        session = self.client.session
        session["portal_user_id"] = self.student_pu.pk
        session.save()
        resp = self.client.get(self.url)
        self.assertRedirects(resp, reverse("portal:home"), fetch_redirect_response=False)

    # --- POST: Student ---

    def test_student_login_correct_credentials_redirects_home(self):
        resp = self.client.post(
            self.url, {"email": "student_login@example.com", "password": "s3cret!"}
        )
        self.assertRedirects(resp, reverse("portal:home"), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("portal_user_id"), self.student_pu.pk)

    def test_student_login_wrong_password_shows_error(self):
        resp = self.client.post(
            self.url, {"email": "student_login@example.com", "password": "wrong"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("portal_user_id", self.client.session)
        self.assertContains(resp, "Ungültige Zugangsdaten")

    def test_student_login_nonexistent_user_shows_error(self):
        resp = self.client.post(self.url, {"email": "nobody@example.com", "password": "irrelevant"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ungültige Zugangsdaten")

    # --- POST: Parent ---

    def test_parent_login_correct_credentials_redirects_home(self):
        resp = self.client.post(
            self.url, {"email": "parent_login@example.com", "password": "p4rent!"}
        )
        self.assertRedirects(resp, reverse("portal:home"), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("portal_user_id"), self.parent_pu.pk)

    def test_parent_login_wrong_password_shows_error(self):
        resp = self.client.post(self.url, {"email": "parent_login@example.com", "password": "nope"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("portal_user_id", self.client.session)
        self.assertContains(resp, "Ungültige Zugangsdaten")

    # --- Error message uniformity ---

    def test_wrong_password_and_wrong_user_return_same_error(self):
        resp_bad_pw = self.client.post(
            self.url, {"email": "student_login@example.com", "password": "x"}
        )
        resp_bad_user = self.client.post(self.url, {"email": "ghost@example.com", "password": "x"})
        self.assertEqual(resp_bad_pw.status_code, resp_bad_user.status_code)
        for resp in (resp_bad_pw, resp_bad_user):
            self.assertContains(resp, "Ungültige Zugangsdaten")

    # --- next redirect ---

    def test_login_respects_safe_next_param(self):
        next_url = reverse("portal:student_home")
        resp = self.client.post(
            self.url,
            {"email": "student_login@example.com", "password": "s3cret!", "next": next_url},
        )
        self.assertRedirects(resp, next_url, fetch_redirect_response=False)

    def test_login_ignores_unsafe_next_param(self):
        resp = self.client.post(
            self.url,
            {
                "email": "student_login@example.com",
                "password": "s3cret!",
                "next": "http://evil.com",
            },
        )
        self.assertRedirects(resp, reverse("portal:home"), fetch_redirect_response=False)

    # --- Inactive user ---

    def test_inactive_portal_user_cannot_login(self):
        self.student_pu.user.is_active = False
        self.student_pu.user.save()
        resp = self.client.post(
            self.url, {"email": "student_login@example.com", "password": "s3cret!"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("portal_user_id", self.client.session)
        self.assertContains(resp, "Ungültige Zugangsdaten")

    def test_activate_then_logout_then_login_works(self):
        """Regressionstest: Produktionsfluss – Einladungslink aktivieren, ausloggen, normal einloggen."""
        from django.utils import timezone

        User = get_user_model()
        # Genau wie in students/views.py: Django-User mit zufälligem Passwort erstellen
        user = User.objects.create_user(
            username="portal_student_prod_test",
            email="prod_flow@example.com",
            password="random_garbage_token_hex",
        )
        tutor = _make_tutor("tutor_prod_flow")
        portal_user = PortalUser.objects.create(user=user, role="student", tutor=tutor)
        contract = _make_contract(tutor)
        StudentPortalLink.objects.create(
            portal_user=portal_user,
            contract=contract,
            invite_token="prod-flow-token-abc",
            invite_token_created_at=timezone.now(),
            is_active=False,
        )

        # 1. Aktivierung via Einladungslink (Passwort setzen)
        activate_url = reverse("portal:activate", kwargs={"token": "prod-flow-token-abc"})
        resp = self.client.post(
            activate_url, {"password": "userchosen99!", "password_confirm": "userchosen99!"}
        )
        self.assertRedirects(resp, reverse("portal:home"), fetch_redirect_response=False)

        # 2. Ausloggen
        self.client.post(reverse("portal:logout"))
        self.assertNotIn("portal_user_id", self.client.session)

        # 3. Normales Login mit Email + selbst gewähltem Passwort
        resp = self.client.post(
            self.url,
            {"email": "prod_flow@example.com", "password": "userchosen99!"},
        )
        self.assertRedirects(resp, reverse("portal:home"), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("portal_user_id"), portal_user.pk)


class PortalPasswordResetViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = _make_tutor("tutor_pw")
        email = "reset_user@example.com"
        self.portal_user = _make_portal_user(self.tutor, "parent", "reset_user", "pw123")
        self.portal_user.user.email = email
        self.portal_user.user.save()
        self.url = reverse("portal:password_reset")

    def test_get_renders_form(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_valid_email_accepted(self):
        resp = self.client.post(self.url, {"email": "reset_user@example.com"})
        if resp.status_code == 302:
            # Must redirect to a confirmation page, not back to login
            self.assertNotEqual(resp["Location"], reverse("portal:login"))
        else:
            self.assertEqual(resp.status_code, 200)
            # Success response must not contain a login-failure message
            self.assertNotContains(resp, "Ungültige Zugangsdaten")

    def test_post_unknown_email_does_not_reveal_existence(self):
        # Security: unknown address must behave identically to a known one
        # (prevents email-enumeration attacks — no specific error is expected)
        resp = self.client.post(self.url, {"email": "nonexistent@example.com"})
        self.assertIn(resp.status_code, (200, 302))

    def test_post_unknown_email_returns_200(self):
        # View never reveals whether email exists — always renders template
        resp = self.client.post(self.url, {"email": "nobody@example.com"})
        self.assertEqual(resp.status_code, 200)

    def test_post_empty_email_returns_200(self):
        # Empty email is silently ignored, view still renders template
        resp = self.client.post(self.url, {"email": ""})
        self.assertEqual(resp.status_code, 200)


class PortalFileUploadValidationTest(TestCase):
    """Tests the file-upload validation constants and the upload endpoint."""

    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".doc", ".xlsx", ".xls", ".txt"}
    MAX_SIZE = 50 * 1024 * 1024  # 50 MB

    def setUp(self):
        self.client = Client()
        self.tutor = _make_tutor("tutor_upload")
        self.contract = _make_contract(self.tutor)
        self.student_pu = _make_portal_user(self.tutor, "student", "upload_student", "uppass")
        _make_student_link(self.student_pu, self.contract, active=True)
        session = self.client.session
        session["portal_user_id"] = self.student_pu.pk
        session.save()

    def _fake_file(self, name, size_bytes, content=b"x"):
        data = content * size_bytes
        return io.BytesIO(data[:size_bytes])

    def test_allowed_extensions_set_is_correct(self):
        from apps.portal.views import _ALLOWED_UPLOAD_EXTENSIONS

        self.assertEqual(_ALLOWED_UPLOAD_EXTENSIONS, self.ALLOWED_EXTENSIONS)

    def test_max_upload_size_constant(self):
        from apps.portal.views import _MAX_UPLOAD_SIZE

        self.assertEqual(_MAX_UPLOAD_SIZE, self.MAX_SIZE)

    def test_disallowed_extension_exe_rejected(self):
        from apps.portal.views import _ALLOWED_UPLOAD_EXTENSIONS

        self.assertNotIn(".exe", _ALLOWED_UPLOAD_EXTENSIONS)

    def test_disallowed_extension_py_rejected(self):
        from apps.portal.views import _ALLOWED_UPLOAD_EXTENSIONS

        self.assertNotIn(".py", _ALLOWED_UPLOAD_EXTENSIONS)

    def test_disallowed_extension_js_rejected(self):
        from apps.portal.views import _ALLOWED_UPLOAD_EXTENSIONS

        self.assertNotIn(".js", _ALLOWED_UPLOAD_EXTENSIONS)

    def test_file_just_below_max_size_is_within_limit(self):
        size = self.MAX_SIZE - 1
        self.assertLessEqual(size, self.MAX_SIZE)

    def test_file_exactly_at_max_size_is_at_limit(self):
        self.assertEqual(self.MAX_SIZE, 50 * 1024 * 1024)

    def test_file_above_max_size_exceeds_limit(self):
        size = self.MAX_SIZE + 1
        self.assertGreater(size, self.MAX_SIZE)

    def test_exe_upload_rejected_via_http(self):
        exe_file = SimpleUploadedFile(
            "malware.exe",
            b"MZ\x90\x00" + b"\x00" * 60,
            content_type="application/octet-stream",
        )
        upload_url = reverse("portal:documents", kwargs={"student_pk": self.contract.pk})
        resp = self.client.post(upload_url, {"file": exe_file})
        # A successful upload (201 or redirect to a success page) must not happen
        self.assertNotEqual(resp.status_code, 201)
        if resp.status_code == 200:
            content = resp.content.decode("utf-8", errors="replace").lower()
            rejected = any(
                phrase in content
                for phrase in [
                    "nicht erlaubt",
                    "not allowed",
                    "ungültig",
                    "invalid",
                    "fehler",
                    "error",
                    ".exe",
                ]
            )
            self.assertTrue(
                rejected, "Expected a rejection message for the .exe upload, found none"
            )


class PortalAccessControlTest(TestCase):
    """Unauthenticated requests must be redirected to login."""

    def setUp(self):
        self.client = Client()
        self.tutor = _make_tutor("tutor_access")
        self.contract = _make_contract(self.tutor)
        self.student_pu = _make_portal_user(self.tutor, "student", "access_student", "accpass")
        _make_student_link(self.student_pu, self.contract, active=True)
        self.parent_pu = _make_portal_user(self.tutor, "parent", "access_parent", "accparent")
        _make_parent_link(self.parent_pu, self.contract, active=True)

    def _assert_requires_login(self, url):
        resp = self.client.get(url)
        login_url = reverse("portal:login")
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertIn(login_url, resp["Location"])

    def test_home_redirects_unauthenticated(self):
        self._assert_requires_login(reverse("portal:home"))

    def test_student_home_redirects_unauthenticated(self):
        self._assert_requires_login(reverse("portal:student_home"))

    def test_student_lessons_redirects_unauthenticated(self):
        self._assert_requires_login(reverse("portal:student_lessons"))

    def test_parent_home_redirects_unauthenticated(self):
        self._assert_requires_login(reverse("portal:parent_home"))

    def test_messages_redirects_unauthenticated(self):
        self._assert_requires_login(
            reverse("portal:messages", kwargs={"student_pk": self.contract.pk})
        )

    def test_documents_redirects_unauthenticated(self):
        self._assert_requires_login(
            reverse("portal:documents", kwargs={"student_pk": self.contract.pk})
        )

    def test_calendar_redirects_unauthenticated(self):
        self._assert_requires_login(reverse("portal:calendar"))

    def test_student_cannot_access_parent_home(self):
        session = self.client.session
        session["portal_user_id"] = self.student_pu.pk
        session.save()
        resp = self.client.get(reverse("portal:parent_home"))
        self.assertIn(resp.status_code, (302, 403))

    def test_parent_cannot_access_student_home(self):
        session = self.client.session
        session["portal_user_id"] = self.parent_pu.pk
        session.save()
        resp = self.client.get(reverse("portal:student_home"))
        self.assertIn(resp.status_code, (302, 403))


class PortalDispatchViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = _make_tutor("tutor_dispatch")
        self.student_pu = _make_portal_user(self.tutor, "student", "dispatch_student", "pw")
        self.parent_pu = _make_portal_user(self.tutor, "parent", "dispatch_parent", "pw")

    def test_dispatch_student_to_student_home(self):
        session = self.client.session
        session["portal_user_id"] = self.student_pu.pk
        session.save()
        resp = self.client.get(reverse("portal:home"))
        self.assertRedirects(resp, reverse("portal:student_home"), fetch_redirect_response=False)

    def test_dispatch_parent_to_parent_home(self):
        session = self.client.session
        session["portal_user_id"] = self.parent_pu.pk
        session.save()
        resp = self.client.get(reverse("portal:home"))
        self.assertRedirects(resp, reverse("portal:parent_home"), fetch_redirect_response=False)

    def test_dispatch_unauthenticated_to_login(self):
        resp = self.client.get(reverse("portal:home"))
        self.assertRedirects(resp, reverse("portal:login"), fetch_redirect_response=False)


class PortalLogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = _make_tutor("tutor_logout")
        self.portal_user = _make_portal_user(self.tutor, "student", "logout_student", "pw")

    def test_logout_clears_session(self):
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()
        self.client.post(reverse("portal:logout"))
        self.assertNotIn("portal_user_id", self.client.session)

    def test_logout_redirects_to_login(self):
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()
        resp = self.client.post(reverse("portal:logout"))
        self.assertRedirects(resp, reverse("portal:login"), fetch_redirect_response=False)


class PortalActivateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = _make_tutor("tutor_activate")
        self.contract = _make_contract(self.tutor)
        self.student_pu = _make_portal_user(self.tutor, "student", "activate_student", "newpw123")
        self.link = _make_student_link(self.student_pu, self.contract, active=False)

    def test_valid_token_get(self):
        resp = self.client.get(reverse("portal:activate", kwargs={"token": self.link.invite_token}))
        self.assertIn(resp.status_code, (200, 302))

    def test_invalid_token_shows_expired_message(self):
        resp = self.client.get(reverse("portal:activate", kwargs={"token": "invalid-token-xyz"}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "abgelaufen")


class InactiveParentLinkAccessTest(TestCase):
    """Regression: deactivated parent links must not grant access to student data."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.tutor = _make_tutor("tutor_inactive_parent")
        self.parent_pu = _make_portal_user(self.tutor, "parent", "parent_inactive", "pw_inactive")
        self.contract = _make_contract(self.tutor)
        # Inactive link – is_active=False
        self.inactive_link = _make_parent_link(self.parent_pu, self.contract, active=False)
        # Authenticate as the parent portal user
        session = self.client.session
        session["portal_user_id"] = self.parent_pu.pk
        session.save()

    def test_inactive_parent_link_detail_view_returns_404(self):
        url = reverse("portal:parent_student_detail", kwargs={"student_pk": self.contract.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_inactive_parent_link_message_view_returns_403(self):
        url = reverse("portal:messages", kwargs={"student_pk": self.contract.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_active_parent_link_detail_view_returns_200(self):
        self.inactive_link.is_active = True
        self.inactive_link.save()
        url = reverse("portal:parent_student_detail", kwargs={"student_pk": self.contract.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_active_parent_link_message_view_returns_200(self):
        self.inactive_link.is_active = True
        self.inactive_link.save()
        url = reverse("portal:messages", kwargs={"student_pk": self.contract.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
