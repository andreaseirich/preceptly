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
        self.assertIn(b"sitemap.xml", self.response.content)
