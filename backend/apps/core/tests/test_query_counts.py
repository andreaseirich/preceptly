"""Die Zahl der Datenbankabfragen der meistgenutzten Seiten darf nicht mit den
Daten wachsen - sonst wird aus einer Liste unbemerkt eine Abfrage pro Eintrag
(„N+1“). Prüfbericht 27.09.2026, L2.

Gemessen wird dieselbe Seite mit wenig und mit viel Daten, nicht gegen eine
feste Zahl: So bricht der Test nicht bei jeder harmlosen Änderung, fängt aber
genau das Wachstum ab. Vor jeder Messung ein Aufruf zum Aufwärmen, weil einige
Context-Processors Werte kurz cachen.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.billing.services import InvoiceService
from apps.contracts.models import Contract
from apps.core.models import UserProfile
from apps.lessons.models import Lesson
from apps.portal.tests_portal import _make_portal_user, _make_student_link


class QueryCountTest(TestCase):
    def setUp(self):
        cache.clear()
        self.tutor = User.objects.create_user("lehrer", password="pw", email="l@example.com")
        UserProfile.objects.create(user=self.tutor, subscription_tier="pro")
        today = date.today()
        self.monday = today - timedelta(days=today.weekday())
        self.last_month_end = today.replace(day=1) - timedelta(days=1)
        self.last_month_start = self.last_month_end.replace(day=1)
        self.counter = 0

    def _contract(self):
        self.counter += 1
        return Contract.objects.create(
            user=self.tutor,
            first_name=f"Schüler{self.counter}",
            last_name="Test",
            hourly_rate=Decimal("25.00"),
            unit_duration_minutes=60,
            start_date=self.last_month_start,
        )

    def _week_lessons(self, contract, count=3):
        for day in range(count):
            Lesson.objects.create(
                contract=contract,
                date=self.monday + timedelta(days=day % 5),
                start_time=time(8 + day % 10, 0),
                duration_minutes=60,
                status="planned",
            )

    def _add_students(self, n):
        """n Schüler mit Stunden in dieser Woche und je einer Rechnung vom Vormonat."""
        for _ in range(n):
            contract = self._contract()
            self._week_lessons(contract)
            Lesson.objects.create(
                contract=contract,
                date=self.last_month_start + timedelta(days=2),
                start_time=time(15, 0),
                duration_minutes=60,
                status="taught",
            )
            InvoiceService.create_invoice_from_lessons(
                self.last_month_start, self.last_month_end, contract=contract, user=self.tutor
            )

    def _count(self, url):
        self.client.get(url)  # aufwärmen
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx.captured_queries)

    def _assert_flat(self, url, grow):
        few = self._count(url)
        grow()
        many = self._count(url)
        self.assertLessEqual(many, few, f"{url}: {few} Abfragen mit wenig Daten, {many} mit viel")

    def test_week_view(self):
        self.client.force_login(self.tutor)
        self._add_students(2)
        self._assert_flat(reverse("lessons:week"), lambda: self._add_students(6))

    def test_dashboard(self):
        self.client.force_login(self.tutor)
        self._add_students(2)
        self._assert_flat(reverse("core:dashboard"), lambda: self._add_students(6))

    def test_invoice_list(self):
        self.client.force_login(self.tutor)
        self._add_students(2)
        self._assert_flat(reverse("billing:invoice_list"), lambda: self._add_students(6))

    def test_portal_student_home(self):
        contract = self._contract()
        student = _make_portal_user(self.tutor, "student", "schueler", "Portal-Passwort-1")
        _make_student_link(student, contract, active=True)
        self._week_lessons(contract, 2)
        session = self.client.session
        session["portal_user_id"] = student.pk
        session.save()

        self._assert_flat(reverse("portal:student_home"), lambda: self._week_lessons(contract, 10))
