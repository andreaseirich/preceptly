from django.test import TestCase


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
