import re

from django.test import TestCase


class OgTitleParityTest(TestCase):
    """og:title must mirror the page <title> so social previews match browser tabs."""

    def test_landing_og_title_matches_title(self):
        response = self.client.get("/")
        html = response.content.decode()
        title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        og_match = re.search(r'<meta property="og:title" content="(.*?)"', html)
        self.assertIsNotNone(title_match, "<title> not found in landing page")
        self.assertIsNotNone(og_match, "og:title not found in landing page")
        self.assertEqual(
            title_match.group(1).strip(),
            og_match.group(1).strip(),
            "og:title does not match <title> on the landing page",
        )


class RobotsTxtTest(TestCase):
    def setUp(self):
        self.response = self.client.get("/robots.txt")

    def test_returns_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_content_type_is_text_plain(self):
        self.assertIn("text/plain", self.response.get("Content-Type", ""))

    def test_disallows_portal(self):
        self.assertIn(b"Disallow: /portal/", self.response.content)

    def test_allows_all(self):
        self.assertIn(b"Allow: /", self.response.content)

    def test_contains_sitemap_reference(self):
        self.assertIn(b"Sitemap:", self.response.content)
        self.assertIn(b"preceptly.de/sitemap.xml", self.response.content)

    def test_faq_not_disallowed(self):
        self.assertNotIn(b"Disallow: /faq/", self.response.content)


class SitemapTest(TestCase):
    def setUp(self):
        self.response = self.client.get("/sitemap.xml")

    def test_returns_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_content_type_is_xml(self):
        self.assertIn("xml", self.response.get("Content-Type", ""))

    def test_contains_landing_url(self):
        self.assertIn(b"<loc>", self.response.content)

    def test_contains_imprint_url(self):
        self.assertIn(b"/legal/imprint/", self.response.content)

    def test_contains_privacy_url(self):
        self.assertIn(b"/legal/privacy/", self.response.content)

    def test_does_not_contain_portal(self):
        self.assertNotIn(b"/portal/", self.response.content)

    def test_does_not_contain_login(self):
        self.assertNotIn(b"/login/", self.response.content)

    def test_contains_faq_url(self):
        self.assertIn(b"/faq/", self.response.content)


class FaqPageAccessTest(TestCase):
    """FAQ is listed in robots.txt/sitemap.xml and shown to anonymous
    visitors in the nav — it must not require login."""

    def test_anonymous_visitor_gets_200(self):
        response = self.client.get("/faq/")
        self.assertEqual(response.status_code, 200)

    def test_anonymous_visitor_not_redirected_to_login(self):
        response = self.client.get("/faq/")
        self.assertNotEqual(response.status_code, 302)
