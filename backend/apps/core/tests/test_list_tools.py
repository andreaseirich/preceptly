"""Listen: Alle Einträge sind erreichbar, und man kann sortieren und filtern.

Meldung von Andreas, 18.11.2026: "Es werden nicht alle Schüler in der Tabelle angezeigt." Ursache: Die Listen schnitten bei 20
bzw. 50 Einträgen ab (`paginate_by`), aber in keiner Vorlage gab es einen Weg zur nächsten Seite. Im Betrieb betraf das ein Konto
mit 28 Schülern und 299 Stunden. Dazu fehlten Sortierung und (fast überall) Filter.

Geprüft wird je Liste: jede Seite erreichbar, kein Eintrag fehlt oder doppelt, Sortierung (nur über eine feste Liste von
Schlüsseln), Filter, fremde Daten bleiben draußen, Eingaben werden maskiert.
"""

import re
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import Invoice
from apps.contracts.models import Contract, Institute
from apps.core.models import Expense, UserProfile
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.portal.models import ProgressNote


class ListTestCase(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user(
            "liste_tutor", password="pw", email="liste@example.com"
        )
        UserProfile.objects.create(user=self.tutor, subscription_tier="pro")
        self.client.force_login(self.tutor)
        self.counter = 0

    def student(self, first=None, last="Test", user=None, **kwargs):
        self.counter += 1
        defaults = {
            "first_name": first or f"Schüler{self.counter:03d}",
            "last_name": last,
            "hourly_rate": Decimal("25.00"),
            "unit_duration_minutes": 60,
            "start_date": date(2026, 1, 1),
        }
        return Contract.objects.create(user=user or self.tutor, **{**defaults, **kwargs})

    def students(self, n):
        return [self.student() for _ in range(n)]

    def get(self, name, **params):
        return self.client.get(reverse(name), params)

    def names_on_every_page(self, name, context_key, **params):
        """Alle Seiten abrufen; liefert die Listen je Seite und die Zahl der Seiten."""
        first = self.get(name, **params)
        pages = first.context["paginator"].num_pages
        result = []
        for number in range(1, pages + 1):
            response = self.get(name, page=number, **params)
            self.assertEqual(response.status_code, 200)
            result.append(list(response.context[context_key]))
        return result, pages


class StudentPagesTest(ListTestCase):
    def test_every_student_is_reachable_through_the_pages(self):
        created = self.students(45)

        pages, count = self.names_on_every_page("contracts:list", "contracts")

        self.assertEqual(count, 3)
        self.assertEqual([len(p) for p in pages], [20, 20, 5])
        shown = [c.pk for page in pages for c in page]
        self.assertEqual(len(shown), len(set(shown)), "ein Schüler steht auf zwei Seiten")
        self.assertEqual(set(shown), {c.pk for c in created}, "ein Schüler fehlt")

    def test_pages_stay_stable_when_many_students_have_the_same_sort_value(self):
        # Ohne eindeutigen Schluss am Ende der Sortierung dürfte die Datenbank gleiche Werte je Abfrage anders ordnen:
        # Dann stünde ein Schüler auf zwei Seiten und ein anderer auf keiner.
        created = [self.student(first="Gleich", last="Name") for _ in range(45)]

        for sort in ("student", "institute", "rate", "status"):
            for direction in ("asc", "desc"):
                with self.subTest(sort=sort, dir=direction):
                    pages, _count = self.names_on_every_page(
                        "contracts:list", "contracts", sort=sort, dir=direction
                    )
                    shown = [c.pk for page in pages for c in page]
                    self.assertEqual(
                        len(shown), len(set(shown)), "ein Schüler steht auf zwei Seiten"
                    )
                    self.assertEqual(set(shown), {c.pk for c in created}, "ein Schüler fehlt")

    def test_the_student_page_also_works_for_the_other_student_list(self):
        created = self.students(45)

        pages, count = self.names_on_every_page("students:list", "students")

        self.assertEqual(count, 3)
        self.assertEqual({c.pk for page in pages for c in page}, {c.pk for c in created})

    def test_the_page_offers_a_way_to_the_next_and_previous_page(self):
        self.students(45)

        first = self.get("contracts:list").content.decode()
        last = self.get("contracts:list", page=3).content.decode()

        self.assertIn('class="pager" role="navigation" aria-label=', first)
        self.assertNotIn(
            '<nav class="pager"', first, "base.html stylt jedes nav als dunkle Menüleiste"
        )
        self.assertIn('rel="next"', first)
        self.assertNotIn('rel="prev"', first)
        self.assertIn("?page=2", first)
        self.assertIn('rel="prev"', last)
        self.assertNotIn('rel="next"', last)
        self.assertIn('aria-current="page"', last)

    def test_the_summary_says_how_many_entries_there_are(self):
        self.students(45)

        html = self.get("contracts:list", page=2).content.decode()

        summary = re.search(r'<p class="pager-summary">(.*?)</p>', html, re.S).group(1)
        for number in ("21", "40", "45"):
            self.assertIn(number, summary)

    def test_one_page_shows_no_page_links_but_still_the_count(self):
        self.students(3)

        html = self.get("contracts:list").content.decode()

        self.assertNotIn('class="pager" role="navigation"', html)
        self.assertIn("pager-summary", html)

    def test_a_wrong_page_number_never_gives_an_error(self):
        self.students(45)

        for page, expected in (("abc", 1), ("0", 3), ("-4", 3), ("999", 3), ("", 1)):
            with self.subTest(page=page):
                response = self.get("contracts:list", page=page)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["page_obj"].number, expected)

    def test_other_tutors_students_are_never_listed(self):
        self.students(3)
        other = User.objects.create_user("fremd", password="pw")
        for _ in range(30):
            self.student(user=other)

        response = self.get("contracts:list")

        self.assertEqual(response.context["paginator"].count, 3)


class StudentSortTest(ListTestCase):
    def setUp(self):
        super().setUp()
        for first in ("bernd", "Anna", "carl", "Dora"):
            self.student(first=first, last="Meier")

    def order(self, **params):
        return [c.first_name for c in self.get("contracts:list", **params).context["contracts"]]

    def test_names_sort_without_regard_to_case_in_both_directions(self):
        self.assertEqual(self.order(sort="student", dir="asc"), ["Anna", "bernd", "carl", "Dora"])
        self.assertEqual(self.order(sort="student", dir="desc"), ["Dora", "carl", "bernd", "Anna"])

    def test_without_a_choice_the_list_is_sorted_by_name(self):
        self.assertEqual(self.order(), ["Anna", "bernd", "carl", "Dora"])

    def test_the_active_column_is_marked_and_a_second_click_reverses_it(self):
        html = self.get("contracts:list", sort="student", dir="asc").content.decode()

        header = re.search(r'<th scope="col" aria-sort="ascending"><a[^>]*href="([^"]*)"', html)
        self.assertIsNotNone(header, "die aktive Spalte trägt aria-sort")
        self.assertIn("dir=desc", header.group(1))
        self.assertEqual(html.count("aria-sort="), 1, "nur die aktive Spalte")

    def test_numbers_sort_as_numbers_and_empty_values_come_last(self):
        Contract.objects.filter(first_name="Anna").update(hourly_rate=Decimal("9.00"))
        Contract.objects.filter(first_name="bernd").update(hourly_rate=Decimal("100.00"))
        Contract.objects.filter(first_name="Dora").update(end_date=date(2026, 6, 1))
        Contract.objects.filter(first_name="carl").update(end_date=date(2026, 3, 1))

        self.assertEqual(self.order(sort="rate", dir="asc")[0], "Anna")
        self.assertEqual(
            self.order(sort="rate", dir="desc")[0], "bernd"
        )  # 100 vor 25 (nicht als Text)
        for direction in ("asc", "desc"):
            order = self.order(sort="to", dir=direction)
            self.assertEqual(
                set(order[-2:]),
                {"Anna", "bernd"},
                f"Schüler ohne Ende stehen zuletzt ({direction})",
            )

    def test_an_unknown_sort_key_is_ignored_and_never_reaches_the_database(self):
        for key in ("user__password", "pk; DROP TABLE x", "-first_name", "student__"):
            with self.subTest(key=key):
                response = self.get("contracts:list", sort=key, dir="asc")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["list_sort"], "student")

    def test_the_default_direction_belongs_to_the_default_column_only(self):
        # Rechnungen und Stunden zeigen standardmäßig das Neueste zuerst. Eine andere Spalte ohne Richtung: aufsteigend.
        self.invoice_page = self.get("billing:invoice_list")
        self.assertEqual(
            (self.invoice_page.context["list_sort"], self.invoice_page.context["list_dir"]),
            ("created", "desc"),
        )
        other = self.get("billing:invoice_list", sort="payer")
        self.assertEqual((other.context["list_sort"], other.context["list_dir"]), ("payer", "asc"))
        again = self.get("billing:invoice_list", sort="created")
        self.assertEqual(again.context["list_dir"], "desc")

    def test_an_unknown_direction_falls_back_to_the_default(self):
        response = self.get("contracts:list", sort="student", dir="sideways")

        self.assertEqual(response.context["list_dir"], "asc")

    def test_sorting_keeps_the_filters_and_starts_on_page_one(self):
        html = self.get("contracts:list", q="Meier", page=1).content.decode()

        link = re.search(r'<th scope="col"><a class="sort-link" href="([^"]*)"', html).group(1)
        self.assertIn("q=Meier", link)
        self.assertNotIn("page=", link)


class StudentFilterTest(ListTestCase):
    def setUp(self):
        super().setUp()
        self.institute = Institute.objects.create(user=self.tutor, institute_name="Abacus")
        self.anna = self.student(
            first="Anna", last="Müller", school="Goethe-Gymnasium", institute_fk=self.institute
        )
        self.bernd = self.student(
            first="Bernd", last="Schulz", school="Realschule", is_active=False
        )
        self.carla = self.student(first="Carla", last="Müller", school="Goethe-Gymnasium")

    def found(self, **params):
        return {c.pk for c in self.get("contracts:list", **params).context["contracts"]}

    def test_search_matches_name_school_and_institute(self):
        self.assertEqual(self.found(q="anna"), {self.anna.pk})
        self.assertEqual(self.found(q="müller"), {self.anna.pk, self.carla.pk})
        self.assertEqual(self.found(q="goethe"), {self.anna.pk, self.carla.pk})
        self.assertEqual(self.found(q="abacus"), {self.anna.pk})

    def test_every_word_of_the_search_must_match(self):
        self.assertEqual(self.found(q="Anna Müller"), {self.anna.pk})
        self.assertEqual(self.found(q="Anna Schulz"), set())

    def test_status_filter(self):
        self.assertEqual(self.found(status="inactive"), {self.bernd.pk})
        self.assertEqual(self.found(status="active"), {self.anna.pk, self.carla.pk})
        self.assertEqual(
            self.found(status="nonsense"), {self.anna.pk, self.bernd.pk, self.carla.pk}
        )

    def test_institute_filter_including_private_lessons(self):
        self.assertEqual(self.found(institute=str(self.institute.pk)), {self.anna.pk})
        self.assertEqual(self.found(institute="none"), {self.bernd.pk, self.carla.pk})

    def test_another_tutors_institute_is_neither_offered_nor_accepted(self):
        other = User.objects.create_user("fremd2", password="pw")
        foreign = Institute.objects.create(user=other, institute_name="GeheimInstitut")

        response = self.get("contracts:list", institute=str(foreign.pk))

        self.assertNotIn("GeheimInstitut", response.content.decode())
        self.assertEqual(
            response.context["paginator"].count, 3, "ein fremdes Institut wirkt nicht als Filter"
        )

    def test_filters_combine(self):
        self.assertEqual(self.found(q="müller", institute="none"), {self.carla.pk})

    def test_pages_keep_the_filter(self):
        for _ in range(45):
            self.student(last="Serie")

        html = self.get("contracts:list", q="Serie").content.decode()

        link = re.search(r'<a href="([^"]*)" rel="next"', html).group(1)
        self.assertIn("q=Serie", link)
        self.assertIn("page=2", link)

    def test_the_search_text_is_escaped_in_the_page(self):
        html = self.get("contracts:list", q="<script>alert(1)</script>").content.decode()

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_no_match_says_so_and_offers_a_reset(self):
        response = self.get("contracts:list", q="gibtesnicht", sort="student", dir="desc")

        self.assertTrue(response.context["list_filters_active"])
        html = response.content.decode()
        self.assertIn("list-filter-reset", html)
        self.assertIn(
            "sort=student", re.search(r'<a href="([^"]*)" class="list-filter-reset"', html).group(1)
        )

    def test_the_filter_form_is_labelled_for_screen_readers(self):
        html = self.get("contracts:list").content.decode()

        self.assertIn('role="search"', html)
        ids = re.findall(r'<(?:input|select) [^>]*id="(filter-[a-z_]+)"', html)
        self.assertGreaterEqual(len(ids), 3)
        for field_id in ids:
            self.assertIn(f'<label for="{field_id}">', html)


class OrderingEndsWithPrimaryKeyTest(ListTestCase):
    """Ohne eindeutigen Schluss dürfte die Datenbank gleiche Werte je Abfrage anders ordnen (Eintrag doppelt oder verloren).

    Das Verhalten lässt sich in einer Testtransaktion nicht zuverlässig auslösen, deshalb prüft der Test die Abfrage selbst.
    """

    def test_every_list_ends_its_sort_with_the_primary_key(self):
        lists = {
            "contracts:list": ("student", "institute", "rate", "duration", "from", "to", "status"),
            "students:list": ("name", "school", "grade"),
            "billing:invoice_list": ("number", "payer", "period", "amount", "status", "created"),
            "lessons:list": ("date", "time", "duration", "student", "status"),
            "lessons:recurring_list": ("student", "time", "start", "status"),
            "core:expense_list": ("date", "category", "description", "amount"),
        }
        for name, keys in lists.items():
            for key in ("",) + keys:
                with self.subTest(liste=name, sort=key):
                    response = self.get(name, **({"sort": key} if key else {}))
                    order = response.context["paginator"].object_list.query.order_by
                    self.assertEqual(order[-1], "pk")


class StudentListOtherTest(ListTestCase):
    def test_the_other_student_list_sorts_and_searches_too(self):
        for first, school in (("Zoe", "B-Schule"), ("Adam", "C-Schule"), ("Mia", "A-Schule")):
            self.student(first=first, school=school)

        by_school = [
            s.first_name for s in self.get("students:list", sort="school").context["students"]
        ]
        found = [s.first_name for s in self.get("students:list", q="adam").context["students"]]

        self.assertEqual(by_school, ["Mia", "Zoe", "Adam"])
        self.assertEqual(found, ["Adam"])


class InvoicePagesTest(ListTestCase):
    def invoice(self, n, owner=None, **kwargs):
        defaults = {
            "owner": owner or self.tutor,
            "payer_name": f"Zahler{n:02d}",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 28),
            "total_amount": Decimal(n),
            "status": "draft",
        }
        return Invoice.objects.create(**{**defaults, **kwargs})

    def test_every_invoice_is_reachable_through_the_pages(self):
        created = [self.invoice(n) for n in range(1, 46)]

        pages, count = self.names_on_every_page("billing:invoice_list", "invoices")

        self.assertEqual(count, 3)
        self.assertEqual({i.pk for page in pages for i in page}, {i.pk for i in created})

    def test_sorting_by_amount_and_payer(self):
        for n in (5, 30, 12):
            self.invoice(n)

        def amounts(**params):
            return [
                int(i.total_amount)
                for i in self.get("billing:invoice_list", **params).context["invoices"]
            ]

        self.assertEqual(amounts(sort="amount", dir="asc"), [5, 12, 30])
        self.assertEqual(amounts(sort="amount", dir="desc"), [30, 12, 5])
        payers = [
            i.payer_name for i in self.get("billing:invoice_list", sort="payer").context["invoices"]
        ]
        self.assertEqual(payers, ["Zahler05", "Zahler12", "Zahler30"])

    def test_search_and_status_filter_for_the_pro_plan(self):
        self.invoice(1, status="paid", payer_name="Frau Becker")
        self.invoice(2, status="sent", payer_name="Herr Wolf")
        self.invoice(3, status="draft", payer_name="Becker KG")

        def payers(**params):
            return {
                i.payer_name for i in self.get("billing:invoice_list", **params).context["invoices"]
            }

        self.assertEqual(payers(q="becker"), {"Frau Becker", "Becker KG"})
        self.assertEqual(payers(status="sent"), {"Herr Wolf"})
        self.assertEqual(payers(status="paid", q="becker"), {"Frau Becker"})

    def test_the_status_filter_stays_a_pro_feature(self):
        free = User.objects.create_user("gratis", password="pw")
        UserProfile.objects.create(user=free, subscription_tier="free")
        self.client.force_login(free)
        self.invoice(1, owner=free, status="paid")
        self.invoice(2, owner=free, status="draft")

        response = self.get("billing:invoice_list", status="paid")

        self.assertEqual(
            response.context["paginator"].count, 2, "die Statusangabe wirkt im Gratis-Tarif nicht"
        )
        self.assertEqual([f["name"] for f in response.context["list_filters"]], ["q"])
        self.assertNotIn('name="status"', response.content.decode())

    def test_other_tutors_invoices_never_appear(self):
        other = User.objects.create_user("fremd3", password="pw")
        self.invoice(1)
        for n in range(2, 30):
            self.invoice(n, owner=other)

        response = self.get("billing:invoice_list", q="Zahler")

        self.assertEqual(response.context["paginator"].count, 1)


class LessonPagesTest(ListTestCase):
    def setUp(self):
        super().setUp()
        self.contract = self.student(first="Lena", last="Haas")

    def lessons(self, n, contract=None, start=date(2026, 1, 1), **kwargs):
        for i in range(n):
            Lesson.objects.create(
                contract=contract or self.contract,
                date=start + timedelta(days=i),
                start_time=time(10, 0),
                duration_minutes=60,
                status=kwargs.get("status", "planned"),
            )

    def test_every_lesson_is_reachable_through_the_pages(self):
        self.lessons(120)

        pages, count = self.names_on_every_page("lessons:list", "lessons")

        self.assertEqual(count, 3)
        self.assertEqual([len(p) for p in pages], [50, 50, 20])
        shown = [lesson.pk for page in pages for lesson in page]
        self.assertEqual(len(shown), len(set(shown)))
        self.assertEqual(set(shown), set(Lesson.objects.values_list("pk", flat=True)))

    def test_the_newest_lesson_comes_first_by_default_and_can_be_reversed(self):
        self.lessons(5)

        newest = [lesson.date for lesson in self.get("lessons:list").context["lessons"]]
        oldest = [
            lesson.date
            for lesson in self.get("lessons:list", sort="date", dir="asc").context["lessons"]
        ]

        self.assertEqual(newest, sorted(newest, reverse=True))
        self.assertEqual(oldest, sorted(oldest))

    def test_date_range_filter(self):
        self.lessons(31)  # 1. bis 31. Januar

        def dates(**params):
            return [lesson.date for lesson in self.get("lessons:list", **params).context["lessons"]]

        self.assertEqual(len(dates(start_date="2026-01-10", end_date="2026-01-12")), 3)
        self.assertEqual(len(dates(start_date="2026-01-30")), 2)
        self.assertEqual(len(dates(end_date="2026-01-02")), 2)
        self.assertEqual(
            len(dates(start_date="kein-datum", end_date="2026-13-45")),
            31,
            "ungültige Daten werden ignoriert",
        )

    def test_filter_by_student_status_and_name(self):
        other = self.student(first="Jonas", last="Kern")
        self.lessons(3)
        self.lessons(2, contract=other, start=date(2026, 3, 1), status="taught")

        def count(**params):
            return self.get("lessons:list", **params).context["paginator"].count

        self.assertEqual(count(student=str(other.pk)), 2)
        self.assertEqual(count(status="taught"), 2)
        self.assertEqual(count(status="planned"), 3)
        self.assertEqual(count(q="kern"), 2)
        self.assertEqual(count(student="999999"), 5, "unbekannter Schüler: kein Filter")

    def test_sorting_by_student(self):
        other = self.student(first="Anton", last="Ahrens")
        self.lessons(1)
        self.lessons(1, contract=other, start=date(2026, 2, 1))

        names = [
            lesson.contract.last_name
            for lesson in self.get("lessons:list", sort="student").context["lessons"]
        ]

        self.assertEqual(names, ["Ahrens", "Haas"])

    def test_other_tutors_lessons_never_appear(self):
        other = User.objects.create_user("fremd4", password="pw")
        foreign = self.student(user=other)
        self.lessons(2)
        self.lessons(40, contract=foreign, start=date(2026, 5, 1))

        self.assertEqual(self.get("lessons:list").context["paginator"].count, 2)


class SeriesPagesTest(ListTestCase):
    def series(self, contract, **kwargs):
        defaults = {
            "contract": contract,
            "start_date": date(2026, 2, 2),
            "start_time": time(15, 0),
            "duration_minutes": 60,
            "monday": True,
        }
        return RecurringLesson.objects.create(**{**defaults, **kwargs})

    def test_every_series_is_reachable_through_the_pages(self):
        created = [self.series(self.student()) for _ in range(25)]

        pages, count = self.names_on_every_page("lessons:recurring_list", "recurring_lessons")

        self.assertEqual(count, 2)
        self.assertEqual({s.pk for page in pages for s in page}, {s.pk for s in created})

    def test_status_filter_splits_running_ended_and_inactive(self):
        today = timezone.localdate()
        running = self.series(self.student(), end_date=None)
        running_later = self.series(self.student(), end_date=today + timedelta(days=5))
        ended = self.series(self.student(), end_date=today - timedelta(days=1))
        inactive = self.series(self.student(), is_active=False)

        def found(status):
            response = self.get("lessons:recurring_list", status=status)
            return {s.pk for s in response.context["recurring_lessons"]}

        self.assertEqual(found("active"), {running.pk, running_later.pk})
        self.assertEqual(found("ended"), {ended.pk})
        self.assertEqual(found("inactive"), {inactive.pk})

    def test_search_and_sorting(self):
        a = self.series(self.student(first="Zora", last="Alt"), start_time=time(9, 0))
        b = self.series(self.student(first="Yvo", last="Berg"), start_time=time(17, 0))

        def order(**params):
            return [
                s.pk
                for s in self.get("lessons:recurring_list", **params).context["recurring_lessons"]
            ]

        self.assertEqual(order(sort="time", dir="asc"), [a.pk, b.pk])
        self.assertEqual(order(sort="time", dir="desc"), [b.pk, a.pk])
        self.assertEqual(order(q="berg"), [b.pk])


class ExpensePagesTest(ListTestCase):
    def expense(
        self, day, amount="10.00", category="office", description="Material", user=None, percent=100
    ):
        return Expense.objects.create(
            user=user or self.tutor,
            date=day,
            amount=Decimal(amount),
            category=category,
            description=description,
            business_use_percent=percent,
        )

    def test_every_expense_of_the_year_is_reachable_and_the_total_covers_all_pages(self):
        year = timezone.now().year
        for n in range(45):
            self.expense(date(year, 1, 1) + timedelta(days=n), amount="2.00")

        pages, count = self.names_on_every_page("core:expense_list", "expenses")
        response = self.get("core:expense_list", page=3)

        self.assertEqual(count, 3)
        self.assertEqual(sum(len(p) for p in pages), 45)
        self.assertEqual(
            response.context["total_expense"], Decimal("90.00"), "die Summe gilt für alle Seiten"
        )

    def test_without_a_year_the_list_and_the_total_both_mean_the_current_year(self):
        year = timezone.now().year
        self.expense(date(year, 2, 1), amount="10.00")
        self.expense(date(year - 1, 2, 1), amount="500.00")

        response = self.get("core:expense_list")

        self.assertEqual(response.context["paginator"].count, 1)
        self.assertEqual(response.context["total_expense"], Decimal("10.00"))
        self.assertEqual(response.context["year_filter"], year)

    def test_an_earlier_year_can_be_chosen(self):
        year = timezone.now().year
        self.expense(date(year, 2, 1), amount="10.00")
        self.expense(date(year - 1, 2, 1), amount="500.00")

        response = self.get("core:expense_list", year=year - 1)

        self.assertEqual(response.context["total_expense"], Decimal("500.00"))
        self.assertEqual(response.context["year_filter"], year - 1)

    def test_an_invalid_year_means_the_current_year(self):
        year = timezone.now().year
        self.expense(date(year, 2, 1))

        for value in ("abc", "1999", "2026; DROP"):
            with self.subTest(year=value):
                response = self.get("core:expense_list", year=value)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["year_filter"], year)

    def test_category_search_and_sorting(self):
        year = timezone.now().year
        self.expense(date(year, 3, 1), "30.00", "travel", "Zugfahrt")
        self.expense(date(year, 3, 2), "5.00", "office", "Stifte")
        self.expense(date(year, 3, 3), "70.00", "office", "Drucker")

        def descriptions(**params):
            return [
                e.description for e in self.get("core:expense_list", **params).context["expenses"]
            ]

        self.assertEqual(
            descriptions(category="office", sort="amount", dir="desc"), ["Drucker", "Stifte"]
        )
        self.assertEqual(descriptions(q="zug"), ["Zugfahrt"])
        self.assertEqual(
            descriptions(sort="description", dir="asc"), ["Drucker", "Stifte", "Zugfahrt"]
        )

    def test_the_total_follows_the_filter_and_says_so(self):
        year = timezone.now().year
        self.expense(date(year, 3, 1), "30.00", "travel")
        self.expense(date(year, 3, 2), "5.00", "office")

        filtered = self.get("core:expense_list", category="office")
        plain = self.get("core:expense_list")

        self.assertEqual(filtered.context["total_expense"], Decimal("5.00"))
        self.assertTrue(filtered.context["expense_extra_filters"])
        self.assertEqual(plain.context["total_expense"], Decimal("35.00"))
        self.assertFalse(plain.context["expense_extra_filters"])

    def test_the_total_counts_the_business_share_like_the_rows_and_the_tax_pages(self):
        year = timezone.now().year
        self.expense(date(year, 3, 1), "10.00", percent=50)  # die Zeile zeigt 5,00 €
        self.expense(date(year, 3, 2), "20.00", percent=100)

        response = self.get("core:expense_list")

        self.assertEqual(
            response.context["total_expense"], Decimal("25.00"), "früher der Rohbetrag: 30,00 €"
        )

    def test_other_tutors_expenses_never_appear(self):
        other = User.objects.create_user("fremd5", password="pw")
        self.expense(date(timezone.now().year, 3, 1))
        for _ in range(30):
            self.expense(date(timezone.now().year, 3, 2), user=other)

        self.assertEqual(self.get("core:expense_list").context["paginator"].count, 1)


class NothingIsCutOffSilentlyTest(ListTestCase):
    def test_the_dashboard_shows_every_lesson_of_the_next_seven_days(self):
        contract = self.student()
        tomorrow = timezone.localdate() + timedelta(days=1)
        for day in range(7):
            for hour in (9, 15):
                Lesson.objects.create(
                    contract=contract,
                    date=tomorrow + timedelta(days=day),
                    start_time=time(hour, 0),
                    duration_minutes=45,
                    status="planned",
                )

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(len(response.context["upcoming_lessons"]), 14, "früher nur die ersten 10")

    def test_the_contract_page_shows_every_progress_note(self):
        contract = self.student()
        for n in range(15):
            ProgressNote.objects.create(contract=contract, tutor=self.tutor, text=f"Notiz {n}")

        response = self.client.get(reverse("contracts:detail", args=[contract.pk]))

        self.assertEqual(len(response.context["progress_notes"]), 15, "früher nur die letzten 10")
