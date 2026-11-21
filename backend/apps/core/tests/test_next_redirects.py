"""?next=: ein zulässiger interner Rücksprung wird befolgt, externe Ziele werden abgelehnt.

Geprüft in der Anmeldung der Tutor-App, im Portal und in der Sprachwahl. Der Browserlauf (docs/features/feat-designsystem-kladde.md) hat dasselbe mit vier
externen Schreibweisen live bestätigt; diese Tests halten es fest.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import UserProfile
from apps.portal.tests_portal import _make_contract, _make_portal_user, _make_tutor

EXTERNAL = [
    "https://boese.example/phishing",
    "//boese.example/phishing",
    "/\\boese.example",
    "javascript:alert(1)",
    "http://localhost.boese.example/",
]


def _location(response):
    return response["Location"] if response.status_code in (301, 302) else ""


class TutorLoginNextTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "next_tutor", password="pw-next-1", email="next.tutor@example.org"
        )
        UserProfile.objects.update_or_create(user=self.user, defaults={"subscription_tier": "pro"})

    def login(self, next_value):
        return self.client.post(
            reverse("core:login"),
            {"username": "next_tutor", "password": "pw-next-1", "next": next_value},
        )

    def test_an_internal_target_is_followed(self):
        response = self.login("/students/")

        self.assertEqual(_location(response), "/students/")

    def test_external_targets_are_refused_and_the_user_lands_in_the_dashboard(self):
        for target in EXTERNAL:
            with self.subTest(next=target):
                self.client.logout()
                response = self.login(target)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(_location(response), reverse("core:dashboard"))


class LanguageChoiceNextTest(TestCase):
    def test_external_targets_are_refused(self):
        for target in EXTERNAL:
            with self.subTest(next=target):
                response = self.client.post(
                    reverse("set_language"), {"language": "en", "next": target}
                )

                self.assertEqual(response.status_code, 302)
                self.assertNotIn("boese", _location(response))
                self.assertTrue(_location(response).startswith("/"), _location(response))
                self.client.cookies.pop(settings.LANGUAGE_COOKIE_NAME, None)

    def test_an_internal_target_is_followed(self):
        response = self.client.post(reverse("set_language"), {"language": "de", "next": "/faq/"})

        self.assertEqual(_location(response), "/faq/")


class PortalLoginNextTest(TestCase):
    def setUp(self):
        tutor = _make_tutor("tutor_portal_next")
        self.parent = _make_portal_user(tutor, "parent", "eltern_next", "pw-eltern-next-1")
        from apps.portal.tests_portal import _make_student_link

        _make_student_link(self.parent, _make_contract(tutor), active=True)

    def login(self, next_value):
        return self.client.post(
            reverse("portal:login"),
            {"email": self.parent.user.email, "password": "pw-eltern-next-1", "next": next_value},
        )

    def test_external_targets_are_refused(self):
        for target in EXTERNAL:
            with self.subTest(next=target):
                cache.clear()  # die Begrenzung der Anmeldeversuche (HTTP 429) greift sonst nach fünf Anmeldungen
                self.client.logout()
                response = self.login(target)

                self.assertEqual(response.status_code, 302)
                self.assertTrue(_location(response).startswith("/portal/"), _location(response))

    def test_an_internal_portal_target_is_followed(self):
        response = self.login("/portal/faq/")

        self.assertEqual(_location(response), "/portal/faq/")
