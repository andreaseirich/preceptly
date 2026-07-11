from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse


def robots_txt(request):
    site_url = getattr(settings, "SITE_URL", "https://preceptly.de")
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Authenticated / private areas",
        "Disallow: /admin/",
        "Disallow: /portal/",
        "Disallow: /login/",
        "Disallow: /logout/",
        "Disallow: /register/",
        "Disallow: /dashboard/",
        "Disallow: /students/",
        "Disallow: /contracts/",
        "Disallow: /lessons/",
        "Disallow: /blocked-times/",
        "Disallow: /billing/",
        "Disallow: /ai/",
        "Disallow: /lesson-plans/",
        "Disallow: /meetings/",
        "Disallow: /settings/",
        "Disallow: /income/",
        "Disallow: /reports/",
        "Disallow: /messages/",
        "Disallow: /api/",
        "Disallow: /dev/",
        "Disallow: /tax-year/",
        "Disallow: /expenses/",
        "Disallow: /legal/avv/",
        "Disallow: /legal/accept-avv/",
        "Disallow: /webhooks/",
        "Disallow: /stripe/",
        "Disallow: /erecht24/",
        "Disallow: /health/",
        "Disallow: /test-logs/",
        "Disallow: /test-email/",
        "",
        f"Sitemap: {site_url}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


_PUBLIC_PAGES = [
    ("core:landing", 1.0, "weekly"),
    ("core:faq", 0.6, "monthly"),
    ("core:legal_imprint", 0.3, "yearly"),
    ("core:legal_privacy", 0.3, "monthly"),
    ("core:legal_terms", 0.3, "monthly"),
    ("core:legal_about", 0.3, "yearly"),
    ("core:legal_withdrawal", 0.3, "yearly"),
]


class StaticPageSitemap(Sitemap):
    def items(self):
        return _PUBLIC_PAGES

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    def changefreq(self, item):
        return item[2]
