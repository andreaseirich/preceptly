"""Stimmen von Eltern und Schülern auf der Startseite und ihre Moderation (docs/features/feat-portal-bewertungen.md).

Zählen darf nur, was freigegeben ist und eine Einwilligung hat. Die Tutor-Zahlen („aus … Bewertungen von Nachhilfelehrern“) bleiben unberührt. Benutzername und E-Mail eines Portal-Kontos erscheinen nie.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Review
from apps.portal.tests_portal import _make_portal_user, _make_tutor


def landing(client, lang="de"):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
    return client.get(reverse("core:landing"))


class FamilyReviewFixtures(TestCase):
    def setUp(self):
        self.tutor = _make_tutor("tutor_stimmen")
        self.portal = _make_portal_user(self.tutor, "parent", "portal_12_ab12cd34")

    def family(self, **extra):
        data = {
            "user": self.portal.user,
            "source": "parent",
            "rating": 5,
            "comment": "Termine sind jetzt in zwei Minuten gebucht.",
            "display_name": "Anna",
            "publish_consent_at": timezone.now(),
            "is_approved": True,
        }
        data.update(extra)
        return Review.objects.create(**data)


class LandingFamilyReviewsTest(FamilyReviewFixtures):
    def test_an_approved_review_with_consent_is_shown_with_name_and_role(self):
        self.family()

        html = landing(self.client).content.decode()

        self.assertIn("Stimmen von Eltern und Schülern", html)
        self.assertIn("Termine sind jetzt in zwei Minuten gebucht.", html)
        self.assertIn("— Anna, Elternteil", html)

    def test_the_english_page_translates_heading_and_role_but_not_the_comment(self):
        self.family(source="student", display_name="Max", comment="Easy to book.")

        html = landing(self.client, "en").content.decode()

        self.assertIn("Voices of parents and students", html)
        self.assertIn("— Max, student", html)
        self.assertIn("Easy to book.", html)

    def test_username_and_email_of_the_portal_account_never_appear(self):
        self.family()

        html = landing(self.client).content.decode()

        self.assertNotIn("portal_12_ab12cd34", html)
        self.assertNotIn(self.portal.user.email, html)

    def test_what_is_not_approved_or_has_no_consent_or_no_comment_stays_hidden(self):
        self.family(is_approved=False)
        other = _make_portal_user(self.tutor, "parent", "portal_13_x")
        self.family(user=other.user, publish_consent_at=None, comment="Ohne Einwilligung.")
        third = _make_portal_user(self.tutor, "parent", "portal_14_x")
        self.family(user=third.user, comment="")

        html = landing(self.client).content.decode()

        self.assertNotIn("Stimmen von Eltern und Schülern", html)
        self.assertNotIn("Ohne Einwilligung.", html)

    def test_without_family_reviews_the_section_is_missing(self):
        self.assertNotIn("Stimmen von Eltern und Schülern", landing(self.client).content.decode())

    def test_the_tutor_figures_count_tutor_reviews_only(self):
        Review.objects.create(user=self.tutor, rating=4, comment="Gut.", is_approved=True)
        self.family(rating=1)

        context = landing(self.client).context

        self.assertEqual(context["review_count"], 1)
        self.assertEqual(float(context["review_average"]), 4.0)
        self.assertEqual([r.user for r in context["approved_reviews"]], [self.tutor])

    def test_a_tutor_review_keeps_its_place_in_the_tutor_block(self):
        Review.objects.create(
            user=self.tutor, rating=5, comment="Spart mir Zeit.", is_approved=True
        )

        html = landing(self.client).content.decode()

        self.assertIn("Spart mir Zeit.", html)
        self.assertNotIn("Stimmen von Eltern und Schülern", html)

    def test_existing_reviews_are_tutor_reviews(self):
        review = Review.objects.create(user=self.tutor, rating=5)

        self.assertEqual(
            (review.source, review.display_name, review.publish_consent_at), ("tutor", "", None)
        )


class ModerationTest(FamilyReviewFixtures):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("moderator", "m@example.org", "pw")
        self.client.force_login(self.admin)

    def test_approving_needs_consent_and_a_display_name(self):
        for extra in ({"publish_consent_at": None}, {"display_name": ""}):
            with self.subTest(extra=extra):
                Review.objects.all().delete()
                review = self.family(is_approved=False, **extra)

                response = self.client.post(
                    reverse("core:moderate_review", args=[review.pk]), {"action": "approve"}
                )

                review.refresh_from_db()
                self.assertFalse(review.is_approved)
                self.assertTrue(get_messages(response.wsgi_request))

    def test_a_family_review_with_consent_can_be_approved(self):
        review = self.family(is_approved=False)

        self.client.post(reverse("core:moderate_review", args=[review.pk]), {"action": "approve"})

        review.refresh_from_db()
        self.assertTrue(review.is_approved)

    def test_the_page_shows_origin_name_and_consent(self):
        self.family(is_approved=False)
        other = _make_portal_user(self.tutor, "parent", "portal_15_x")
        self.family(
            user=other.user, is_approved=False, publish_consent_at=None, display_name="Berta"
        )

        html = self.client.get(reverse("core:review_moderation")).content.decode()

        self.assertIn("Anna", html)
        self.assertIn("Elternteil", html)
        self.assertIn("Einwilligung", html)
        self.assertIn("ohne Einwilligung", html)
        self.assertNotIn("portal_12_ab12cd34", html)
