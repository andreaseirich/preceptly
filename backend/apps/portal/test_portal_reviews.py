"""Bewertungen von Eltern und Schülern im Portal (docs/features/feat-portal-bewertungen.md).

Berechtigung: Eltern ja, Schüler nur wenn alle verknüpften Verträge volljährig sind. Pflicht: Sterne, Anzeigename und Einwilligung. Aktualisieren setzt die Freigabe zurück,
Zurückziehen löscht nur die eigene Bewertung. Es wird keine E-Mail versendet.
"""

from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Review
from apps.portal.reviews import can_review
from apps.portal.tests_portal import (
    _make_contract,
    _make_parent_link,
    _make_portal_user,
    _make_tutor,
)

GOOD = {
    "rating": "5",
    "comment": "Termine sind jetzt in zwei Minuten gebucht.",
    "display_name": "Anna",
    "consent": "on",
}


class PortalReviewBase(TestCase):
    def setUp(self):
        self.tutor = _make_tutor("tutor_bewertung")
        self.parent = _make_portal_user(self.tutor, "parent", "eltern_bewertung")
        self.parent_contract = _make_contract(self.tutor)
        _make_parent_link(self.parent, self.parent_contract)

    def login(self, portal_user):
        session = self.client.session
        session["portal_user_id"] = portal_user.pk
        session.save()

    def submit(self, **changes):
        data = {**GOOD, **changes}
        data = {k: v for k, v in data.items() if v is not None}
        return self.client.post(reverse("portal:review_submit"), data)

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def student(self, adult, username="schueler_bewertung", links=1):
        portal_user = _make_portal_user(self.tutor, "student", username)
        for _ in range(links):
            contract = _make_contract(self.tutor)
            contract.is_adult = adult
            contract.save(update_fields=["is_adult"])
            _make_parent_link(portal_user, contract)
        return portal_user


class EligibilityTest(PortalReviewBase):
    def test_a_parent_with_an_active_link_may_review(self):
        self.assertTrue(can_review(self.parent))

    def test_a_parent_without_an_active_link_may_not(self):
        lonely = _make_portal_user(self.tutor, "parent", "eltern_ohne_kind")
        _make_parent_link(lonely, _make_contract(self.tutor), active=False)

        self.assertFalse(can_review(lonely))

    def test_a_minor_student_may_not(self):
        self.assertFalse(can_review(self.student(adult=False)))

    def test_an_adult_student_may(self):
        self.assertTrue(can_review(self.student(adult=True)))

    def test_a_student_with_one_minor_contract_among_several_may_not(self):
        portal_user = self.student(adult=True, username="schueler_gemischt")
        minor = _make_contract(self.tutor)
        minor.is_adult = False
        minor.save(update_fields=["is_adult"])
        _make_parent_link(portal_user, minor)

        self.assertFalse(can_review(portal_user))


class SubmitTest(PortalReviewBase):
    def test_a_parent_review_is_stored_unapproved_with_consent_and_name(self):
        self.login(self.parent)

        response = self.submit()

        self.assertRedirects(response, reverse("portal:home"), fetch_redirect_response=False)
        review = Review.objects.get(user=self.parent.user)
        self.assertEqual((review.source, review.rating, review.display_name), ("parent", 5, "Anna"))
        self.assertEqual(review.comment, GOOD["comment"])
        self.assertFalse(review.is_approved)
        self.assertIsNotNone(review.publish_consent_at)
        self.assertEqual(mail.outbox, [])

    def test_an_adult_student_review_has_the_student_source(self):
        student = self.student(adult=True)
        self.login(student)

        self.submit(display_name="Max")

        self.assertEqual(Review.objects.get(user=student.user).source, "student")

    def test_without_consent_nothing_is_stored(self):
        self.login(self.parent)

        response = self.submit(consent=None)

        self.assertFalse(Review.objects.exists())
        self.assertTrue(
            any("Einwilligung" in m for m in self.messages(response)), self.messages(response)
        )

    def test_the_rating_must_be_between_one_and_five(self):
        self.login(self.parent)
        for rating in ("0", "6", "", "abc"):
            with self.subTest(rating=rating):
                self.submit(rating=rating if rating else None)
                self.assertFalse(Review.objects.exists())

    def test_the_display_name_is_required_short_and_never_an_address(self):
        self.login(self.parent)
        for name in (None, "", " ", "A", "x" * 31, "anna@example.org", "http://x.de", "www.x.de"):
            with self.subTest(name=name):
                self.submit(display_name=name)
                self.assertFalse(Review.objects.exists(), name)

    def test_the_comment_is_optional_but_limited(self):
        self.login(self.parent)

        self.submit(comment="")
        self.assertEqual(Review.objects.get().comment, "")
        Review.objects.all().delete()
        self.submit(comment="x" * 1001)

        self.assertFalse(Review.objects.exists())

    def test_a_minor_student_cannot_post_a_review(self):
        student = self.student(adult=False)
        self.login(student)

        self.submit()

        self.assertFalse(Review.objects.exists())

    def test_without_a_portal_login_nothing_is_stored(self):
        response = self.submit()

        self.assertRedirects(response, reverse("portal:login"), fetch_redirect_response=False)
        self.assertFalse(Review.objects.exists())

    def test_submitting_again_updates_the_one_review_and_withdraws_the_approval(self):
        self.login(self.parent)
        self.submit()
        Review.objects.update(is_approved=True)

        self.submit(comment="Jetzt noch besser.")

        review = Review.objects.get()
        self.assertEqual(review.comment, "Jetzt noch besser.")
        self.assertFalse(review.is_approved)

    def test_changing_only_the_display_name_withdraws_the_approval(self):
        self.login(self.parent)
        self.submit()
        Review.objects.update(is_approved=True)

        self.submit(display_name="Anna M.")

        self.assertFalse(Review.objects.get().is_approved)

    def test_an_unchanged_resubmission_keeps_the_approval(self):
        self.login(self.parent)
        self.submit()
        Review.objects.update(is_approved=True)

        self.submit()

        self.assertTrue(Review.objects.get().is_approved)


class WithdrawTest(PortalReviewBase):
    def test_withdrawing_deletes_only_the_own_review(self):
        other = _make_portal_user(self.tutor, "parent", "eltern_zwei")
        _make_parent_link(other, _make_contract(self.tutor))
        self.login(other)
        self.submit(display_name="Berta")
        self.login(self.parent)
        self.submit()

        response = self.client.post(reverse("portal:review_withdraw"))

        self.assertRedirects(response, reverse("portal:home"), fetch_redirect_response=False)
        self.assertFalse(Review.objects.filter(user=self.parent.user).exists())
        self.assertTrue(Review.objects.filter(user=other.user).exists())

    def test_withdrawing_needs_post_and_a_portal_login(self):
        self.login(self.parent)
        self.submit()

        self.assertEqual(self.client.get(reverse("portal:review_withdraw")).status_code, 405)
        self.client.session.flush()
        anonymous = self.client_class()
        response = anonymous.post(reverse("portal:review_withdraw"))

        self.assertRedirects(response, reverse("portal:login"), fetch_redirect_response=False)
        self.assertEqual(Review.objects.count(), 1)


class CardTest(PortalReviewBase):
    def test_the_card_shows_on_the_single_child_home_for_a_parent(self):
        self.login(self.parent)

        html = self.client.get(reverse("portal:student_home")).content.decode()

        self.assertIn("Wie einfach ist die Terminbuchung?", html)
        self.assertIn('name="consent"', html)
        self.assertIn('name="display_name"', html)

    def test_the_card_shows_on_the_family_overview(self):
        _make_parent_link(self.parent, _make_contract(self.tutor))
        self.login(self.parent)

        html = self.client.get(reverse("portal:parent_home")).content.decode()

        self.assertIn("Wie einfach ist die Terminbuchung?", html)

    def test_a_minor_student_does_not_see_the_card(self):
        student = self.student(adult=False)
        self.login(student)

        html = self.client.get(reverse("portal:student_home")).content.decode()

        self.assertNotIn("Wie einfach ist die Terminbuchung?", html)
        self.assertNotIn('name="consent"', html)

    def test_an_adult_student_sees_the_card(self):
        student = self.student(adult=True)
        self.login(student)

        html = self.client.get(reverse("portal:student_home")).content.decode()

        self.assertIn("Wie einfach ist die Terminbuchung?", html)

    def test_after_a_review_the_card_shows_it_its_status_and_the_withdraw_button(self):
        self.login(self.parent)
        self.submit()

        html = self.client.get(reverse("portal:student_home")).content.decode()

        self.assertIn("Bewertung zurückziehen", html)
        self.assertIn("wartet auf Freigabe", html)
        self.assertIn(GOOD["comment"], html)
        Review.objects.update(is_approved=True)
        self.assertIn(
            "veröffentlicht", self.client.get(reverse("portal:student_home")).content.decode()
        )

    def test_the_consent_text_names_what_is_published_and_how_to_withdraw(self):
        self.login(self.parent)

        html = self.client.get(reverse("portal:student_home")).content.decode()

        self.assertIn("Vorname und meine Bewertung öffentlich auf der Startseite", html)
        self.assertIn("jederzeit", html)
        self.assertIn("Bewertung zurückziehen", html)
