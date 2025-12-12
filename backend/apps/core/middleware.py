"""
Custom middleware for TutorFlow.
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Middleware to set Content-Security-Policy header.

    CSP is configured to prevent XSS attacks by disallowing inline scripts and styles.
    All JavaScript and CSS must be loaded from static files.
    """

    def process_response(self, request, response):
        # Only set CSP if enabled in settings
        if getattr(settings, "ENABLE_CSP", True):
            # Conservative CSP policy: no inline scripts/styles
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'self';"
            )
            response["Content-Security-Policy"] = csp_policy
        return response
