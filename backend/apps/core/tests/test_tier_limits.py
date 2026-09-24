"""Tarif-Grenzen, wie sie die Preisseite verspricht.

Free:    keine Dokumente, keine Portal-Buchung, keine Portal-Serien
Starter: 3 Dokumente je Schüler, 3 Portal-Buchungen je Monat, keine Portal-Serien
Pro:     alles unbegrenzt, Serien auch im Portal
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contracts.models import Contract
from apps.core.feature_flags import document_limit
from apps.core.models import UserProfile
from apps.lessons.models import Session
from apps.lessons.recurring_models import RecurringSession
from apps.portal.models import ParentStudentLink, PortalUser
from apps.students.models import StudentDocument

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _pdf(name="blatt.pdf"):
    return SimpleUploadedFile(name, PDF, content_type="application/pdf")


class TierFixture(TestCase):
    tier = "free"

    def setUp(self):
        self.tutor = User.objects.create_user(username=f"tutor_{self.tier}", password="pass")
        UserProfile.objects.update_or_create(
            user=self.tutor, defaults={"subscription_tier": self.tier}
        )
        self.contract = Contract.objects.create(
            user=self.tutor,
            first_name="Lea",
            last_name="Schmidt",
            hourly_rate=Decimal("25.00"),
            start_date=date.today() - timedelta(days=30),
        )
        portal_django = User.objects.create_user(username=f"portal_{self.tier}", password="pass")
        self.portal_user = PortalUser.objects.create(
            user=portal_django, role="student", tutor=self.tutor
        )
        ParentStudentLink.objects.create(
            parent=self.portal_user, contract=self.contract, is_active=True
        )

    # --- Hilfen ---------------------------------------------------------------

    def _as_portal_user(self):
        self.client.logout()
        session = self.client.session
        session["portal_user_id"] = self.portal_user.pk
        session.save()

    def _add_documents(self, n):
        for i in range(n):
            StudentDocument.objects.create(
                student=self.contract, file=_pdf(f"d{i}.pdf"), name=f"Dok {i}"
            )

    def _add_portal_bookings(self, n, months_ago=0):
        for i in range(n):
            s = Session.objects.create(
                contract=self.contract,
                date=date.today() + timedelta(days=10 + i),
                start_time=time(9 + i, 0),
                duration_minutes=60,
                created_via="portal_booking",
            )
            if months_ago:
                Session.objects.filter(pk=s.pk).update(
                    created_at=timezone.now() - timedelta(days=32 * months_ago)
                )

    def _tutor_upload(self):
        self.client.force_login(self.tutor)
        return self.client.post(
            reverse("students:documents", kwargs={"pk": self.contract.pk}),
            {"name": "Neu", "file": _pdf()},
            follow=True,
        )

    def _portal_upload(self):
        self._as_portal_user()
        return self.client.post(
            reverse("portal:documents", kwargs={"student_pk": self.contract.pk}),
            {"name": "Neu", "file": _pdf()},
            follow=True,
        )

    def _portal_book(self, day_offset=3):
        self._as_portal_user()
        return self.client.post(
            reverse("portal:book", kwargs={"student_pk": self.contract.pk}),
            {
                "date": (date.today() + timedelta(days=day_offset)).isoformat(),
                "start_time": "16:00",
            },
        )

    def _new_bookings(self):
        return Session.objects.filter(contract=self.contract, start_time=time(16, 0)).count()


class FreeTierTest(TierFixture):
    tier = "free"

    def test_no_document_quota(self):
        self.assertEqual(document_limit(self.tutor), 0)

    def test_tutor_cannot_upload_documents(self):
        response = self._tutor_upload()

        self.assertContains(response, "Dokumente gibt es ab dem Starter-Tarif.")
        self.assertEqual(StudentDocument.objects.filter(student=self.contract).count(), 0)

    def test_portal_user_cannot_upload_documents(self):
        response = self._portal_upload()

        self.assertContains(response, "keine weiteren Dateien hochgeladen werden")
        self.assertEqual(StudentDocument.objects.filter(student=self.contract).count(), 0)

    def test_portal_booking_is_blocked(self):
        response = self._portal_book()

        self.assertContains(response, "Online-Buchungen sind im Moment nicht möglich.")
        self.assertEqual(self._new_bookings(), 0)


class StarterTierTest(TierFixture):
    tier = "starter"

    def test_three_documents_per_student(self):
        self.assertEqual(document_limit(self.tutor), 3)

    def test_third_document_is_allowed_fourth_is_not(self):
        self._add_documents(2)
        self._tutor_upload()
        self.assertEqual(StudentDocument.objects.filter(student=self.contract).count(), 3)

        response = self._tutor_upload()

        self.assertContains(response, "höchstens 3 Dokumente je Schüler")
        self.assertEqual(StudentDocument.objects.filter(student=self.contract).count(), 3)

    def test_limit_counts_per_student(self):
        self._add_documents(3)
        other = Contract.objects.create(
            user=self.tutor,
            first_name="Max",
            last_name="Muster",
            hourly_rate=Decimal("25.00"),
            start_date=date.today(),
        )
        self.client.force_login(self.tutor)

        self.client.post(
            reverse("students:documents", kwargs={"pk": other.pk}), {"file": _pdf()}, follow=True
        )

        self.assertEqual(StudentDocument.objects.filter(student=other).count(), 1)

    def test_portal_upload_respects_the_same_limit(self):
        self._add_documents(3)

        self._portal_upload()

        self.assertEqual(StudentDocument.objects.filter(student=self.contract).count(), 3)

    def test_documents_page_shows_quota_and_hides_form_when_full(self):
        self._add_documents(1)
        self.client.force_login(self.tutor)
        url = reverse("students:documents", kwargs={"pk": self.contract.pk})

        self.assertContains(self.client.get(url), "1 von 3 Dokumenten")
        self._add_documents(2)
        full = self.client.get(url)
        self.assertContains(full, "alle 3 Dokumente des Starter-Tarifs belegt")
        self.assertNotContains(full, 'type="file"')

    def test_three_portal_bookings_a_month_then_blocked(self):
        self._add_portal_bookings(2)
        self._portal_book(day_offset=3)
        self.assertEqual(self._new_bookings(), 1)

        response = self._portal_book(day_offset=4)

        self.assertContains(response, "Online-Buchungen sind im Moment nicht möglich.")
        self.assertEqual(self._new_bookings(), 1)

    def test_last_months_bookings_do_not_count(self):
        self._add_portal_bookings(3, months_ago=1)

        self._portal_book()

        self.assertEqual(self._new_bookings(), 1)

    def test_booking_page_says_so_before_the_form_is_filled(self):
        self._add_portal_bookings(3)
        self._as_portal_user()

        page = self.client.get(reverse("portal:book", kwargs={"student_pk": self.contract.pk}))

        self.assertContains(page, "Online-Buchungen sind im Moment nicht möglich.")
        self.assertNotContains(page, 'id="booking-form"')

    def test_portal_series_are_not_available(self):
        self._as_portal_user()
        manage = reverse("portal:recurring_manage", kwargs={"student_pk": self.contract.pk})
        create = reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk})

        self.assertNotContains(self.client.get(manage), create)
        self.assertRedirects(self.client.get(create), manage)
        self.client.post(
            create,
            {"start_time": "16:00", "start_date": date.today().isoformat(), "monday": "on"},
        )
        self.assertFalse(RecurringSession.objects.filter(contract=self.contract).exists())

    def test_settings_show_starter_as_current_plan(self):
        self.client.force_login(self.tutor)

        page = self.client.get(reverse("core:settings"))

        self.assertContains(page, '<span class="premium-badge">Starter</span>', html=True)


class ProTierTest(TierFixture):
    tier = "pro"

    def test_documents_unlimited(self):
        self.assertIsNone(document_limit(self.tutor))
        self._add_documents(5)

        self._tutor_upload()

        self.assertEqual(StudentDocument.objects.filter(student=self.contract).count(), 6)

    def test_portal_bookings_unlimited(self):
        self._add_portal_bookings(5)

        self._portal_book()

        self.assertEqual(self._new_bookings(), 1)

    def test_portal_series_allowed(self):
        self._as_portal_user()
        manage = reverse("portal:recurring_manage", kwargs={"student_pk": self.contract.pk})
        create = reverse("portal:recurring_create", kwargs={"student_pk": self.contract.pk})

        self.assertContains(self.client.get(manage), create)
        self.assertEqual(self.client.get(create).status_code, 200)


class PricingConsistencyTest(TestCase):
    """Preisseite und Abo-Karten in der App versprechen dasselbe."""

    def test_no_public_booking_page_advertised(self):
        user = User.objects.create_user(username="t", password="pass")
        self.client.force_login(user)

        settings_page = self.client.get(reverse("core:settings")).content.decode()
        self.client.logout()
        landing = self.client.get(reverse("core:landing")).content.decode()

        for page in (settings_page, landing):
            self.assertNotIn("public booking", page.lower())
            self.assertNotIn("öffentliche buchung", page.lower())

    def test_landing_lists_the_limits(self):
        body = self.client.get(reverse("core:landing")).content.decode()

        self.assertIn("Portal-Buchungen", body)
        self.assertIn("Unbegrenzte Portal-Buchungen und Serien", body)

    def test_old_booking_url_is_gone(self):
        self.assertEqual(self.client.get("/lessons/booking/irgendwas/").status_code, 404)
