"""
Custom middleware for security headers.
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers when DEBUG=False.
    X-Content-Type-Options and HSTS are handled by SecurityMiddleware;
    we add Referrer-Policy, Cross-Origin-Opener-Policy, and optional CSP.
    """

    def process_response(self, request, response):
        if settings.DEBUG:
            return response
        # Referrer-Policy (Django may set via SECURE_REFERRER_POLICY; ensure it)
        if "Referrer-Policy" not in response:
            response["Referrer-Policy"] = getattr(
                settings,
                "SECURE_REFERRER_POLICY",
                "strict-origin-when-cross-origin",
            )
        # Cross-Origin-Opener-Policy
        if "Cross-Origin-Opener-Policy" not in response:
            response["Cross-Origin-Opener-Policy"] = "same-origin"
        # Optional minimal CSP (avoid breaking inline styles in templates)
        csp = getattr(settings, "SECURE_CSP", None)
        if csp and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = csp
        return response
