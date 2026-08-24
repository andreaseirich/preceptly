"""
Regression test: "Neue Einladung senden" (PortalInviteResendView) must not
deactivate an already-active portal link and force the student through
password setup again.

Real bug report: a tutor clicked "resend invite" for a student who already
had a working portal login. The view unconditionally set
link.is_active = False and issued a fresh invite_token, so the student's
existing session/activation link started treating their account as
"not yet activated" again - they ended up unknowingly setting a new
password, and their old (memorized) password stopped working.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.contracts.models import Contract
from apps.portal.models import ParentStudentLink, PortalUser

User = get_user_model()


class ResendInviteDoesNotDeactivateActiveLinkTest(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(
            username="resend_tutor", password="pass", email="tutor@resend.test"
        )
        self.client = Client()
        self.client.login(username="resend_tutor", password="pass")

        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Florian",
            last_name="Test",
            email="florian@example.com",
            hourly_rate=Decimal("20.00"),
            start_date=date(2025, 1, 1),
            unit_duration_minutes=60,
            is_active=True,
        )
        self.portal_django_user = User.objects.create_user(
            username="portal_student_x", email="florian@example.com", password="OldPassw0rd!"
        )
        self.portal_user = PortalUser.objects.create(
            user=self.portal_django_user, role="student", tutor=self.tutor
        )
        self.link = ParentStudentLink.objects.create(
            parent=self.portal_user, contract=self.contract, is_active=True
        )
        self.original_token = self.link.invite_token

    def test_resend_on_active_link_leaves_it_untouched(self):
        response = self.client.post(
            reverse("students:portal_invite_resend", args=[self.contract.pk])
        )
        self.assertEqual(response.status_code, 302)

        self.link.refresh_from_db()
        self.assertTrue(self.link.is_active, "resend must not deactivate an active portal link")
        self.assertEqual(
            self.link.invite_token,
            self.original_token,
            "resend must not rotate the token of an active link",
        )

    def test_old_password_still_works_after_resend_attempt(self):
        self.client.post(reverse("students:portal_invite_resend", args=[self.contract.pk]))

        self.portal_django_user.refresh_from_db()
        self.assertTrue(self.portal_django_user.check_password("OldPassw0rd!"))

    def test_resend_on_pending_link_still_works_as_before(self):
        """The original behavior (issue a fresh token for a not-yet-active
        invite) must still work - only already-active links are protected."""
        self.link.is_active = False
        self.link.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("students:portal_invite_resend", args=[self.contract.pk])
        )
        self.assertEqual(response.status_code, 302)

        self.link.refresh_from_db()
        self.assertFalse(self.link.is_active)
        self.assertNotEqual(self.link.invite_token, self.original_token)
