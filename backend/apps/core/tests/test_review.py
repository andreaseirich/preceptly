"""
Tests for the tutor review/rating feature: submission, admin-only
moderation (reviews never auto-publish), and the public landing page
display.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import Review


class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tutor", password="test")

    def test_review_defaults_to_not_approved(self):
        review = Review.objects.create(user=self.user, rating=5, comment="Toll!")
        self.assertFalse(review.is_approved)

    def test_editing_an_approved_review_un_approves_it(self):
        """A changed opinion must not keep showing the old approved text -
        it needs a fresh look before going public again."""
        review = Review.objects.create(user=self.user, rating=5, comment="Toll!")
        review.is_approved = True
        review.save(update_fields=["is_approved"])

        review.refresh_from_db()
        review.comment = "Doch nicht so toll."
        review.save()

        review.refresh_from_db()
        self.assertFalse(review.is_approved)

    def test_saving_without_changes_keeps_approval(self):
        review = Review.objects.create(user=self.user, rating=4, comment="Gut")
        review.is_approved = True
        review.save(update_fields=["is_approved"])

        review.refresh_from_db()
        review.save()  # no field changes

        review.refresh_from_db()
        self.assertTrue(review.is_approved)


class SubmitReviewViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = User.objects.create_user(username="tutor2", password="test")

    def test_requires_login(self):
        response = self.client.post(
            reverse("core:submit_review"), {"rating": "5", "comment": "Super"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_creates_unapproved_review(self):
        self.client.login(username="tutor2", password="test")
        response = self.client.post(
            reverse("core:submit_review"), {"rating": "5", "comment": "Super Tool!"}
        )
        self.assertEqual(response.status_code, 302)
        review = Review.objects.get(user=self.tutor)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Super Tool!")
        self.assertFalse(review.is_approved)

    def test_resubmitting_updates_existing_review(self):
        self.client.login(username="tutor2", password="test")
        self.client.post(reverse("core:submit_review"), {"rating": "3", "comment": "Ok"})
        self.client.post(reverse("core:submit_review"), {"rating": "5", "comment": "Jetzt super"})
        self.assertEqual(Review.objects.filter(user=self.tutor).count(), 1)
        review = Review.objects.get(user=self.tutor)
        self.assertEqual(review.rating, 5)

    def test_missing_rating_shows_error_without_crashing(self):
        self.client.login(username="tutor2", password="test")
        response = self.client.post(reverse("core:submit_review"), {"comment": "Kein Rating"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.filter(user=self.tutor).exists())


class DashboardReviewBannerTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = User.objects.create_user(username="tutor3", password="test")
        self.client.login(username="tutor3", password="test")

    def test_banner_shown_when_no_review_yet(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertContains(response, 'id="openReviewModal"')

    def test_banner_hidden_after_review_submitted(self):
        Review.objects.create(user=self.tutor, rating=4)
        response = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(response, 'id="openReviewModal"')


class LandingPageReviewDisplayTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_unapproved_review_not_shown(self):
        user = User.objects.create_user(username="hidden", password="test")
        Review.objects.create(user=user, rating=5, comment="Sollte nicht erscheinen")
        response = self.client.get(reverse("core:landing"))
        self.assertNotContains(response, "Sollte nicht erscheinen")

    def test_approved_review_is_shown_with_stars(self):
        user = User.objects.create_user(username="visible", password="test")
        review = Review.objects.create(user=user, rating=4, comment="Wirklich gut!")
        review.is_approved = True
        review.save(update_fields=["is_approved"])

        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "Wirklich gut!")
        self.assertContains(response, "★★★★☆")  # 4 filled, 1 empty star

    def test_average_rating_shown_when_reviews_exist(self):
        user1 = User.objects.create_user(username="rater1", password="test")
        user2 = User.objects.create_user(username="rater2", password="test")
        for user, rating in [(user1, 5), (user2, 3)]:
            r = Review.objects.create(user=user, rating=rating, comment="x")
            r.is_approved = True
            r.save(update_fields=["is_approved"])

        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "4,0")  # average of 5 and 3, German locale formatting


class ReviewModerationViewTest(TestCase):
    """The custom moderation page - Django Admin is deliberately disabled
    for this project (apps/core/tests/test_admin_disabled.py), so this is
    the only way to approve/reject a review."""

    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_user(
            username="mod", password="test", is_superuser=True
        )
        self.regular_user = User.objects.create_user(username="regular", password="test")
        self.review_author = User.objects.create_user(username="author", password="test")
        self.review = Review.objects.create(user=self.review_author, rating=3, comment="Ganz ok")

    def test_non_superuser_cannot_access_moderation_page(self):
        self.client.login(username="regular", password="test")
        response = self.client.get(reverse("core:review_moderation"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("core:review_moderation"))
        self.assertEqual(response.status_code, 302)

    def test_superuser_sees_pending_review(self):
        self.client.login(username="mod", password="test")
        response = self.client.get(reverse("core:review_moderation"))
        self.assertContains(response, "Ganz ok")

    def test_superuser_can_approve(self):
        self.client.login(username="mod", password="test")
        response = self.client.post(
            reverse("core:moderate_review", args=[self.review.pk]), {"action": "approve"}
        )
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_approved)

    def test_superuser_can_reject_an_approved_review(self):
        self.review.is_approved = True
        self.review.save(update_fields=["is_approved"])
        self.client.login(username="mod", password="test")
        response = self.client.post(
            reverse("core:moderate_review", args=[self.review.pk]), {"action": "reject"}
        )
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertFalse(self.review.is_approved)

    def test_non_superuser_cannot_moderate(self):
        self.client.login(username="regular", password="test")
        self.client.post(
            reverse("core:moderate_review", args=[self.review.pk]), {"action": "approve"}
        )
        self.review.refresh_from_db()
        self.assertFalse(self.review.is_approved)

    def test_superuser_can_delete(self):
        self.client.login(username="mod", password="test")
        response = self.client.post(
            reverse("core:moderate_review", args=[self.review.pk]), {"action": "delete"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_non_superuser_cannot_delete(self):
        self.client.login(username="regular", password="test")
        self.client.post(
            reverse("core:moderate_review", args=[self.review.pk]), {"action": "delete"}
        )
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())
