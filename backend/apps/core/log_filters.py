import logging


class SkipNotFound(logging.Filter):
    """Drops Django's per-request "Not Found: /path" warnings. Vulnerability
    scanners fire hundreds of 404s within seconds; logging each one pushed
    the output over Railway's 500 lines/s limit, which then dropped other
    messages too. The access log still records every 404 in one line."""

    def filter(self, record):
        return getattr(record, "status_code", None) != 404
