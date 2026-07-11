from django.conf import settings
from django.http import HttpResponse


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
        "Disallow: /faq/",
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
