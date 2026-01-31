"""
Template filters for lesson-related formatting.
"""

from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def local_hour(datetime_obj):
    """Returns the hour in local timezone."""
    if datetime_obj:
        local_dt = timezone.localtime(datetime_obj)
        return local_dt.hour
    return None


@register.filter
def local_minute(datetime_obj):
    """Returns the minute in local timezone."""
    if datetime_obj:
        local_dt = timezone.localtime(datetime_obj)
        return local_dt.minute
    return None


@register.filter
def local_date(datetime_obj):
    """Returns the date in local timezone."""
    if datetime_obj:
        local_dt = timezone.localtime(datetime_obj)
        return local_dt.date()
    return None


@register.filter
def dict_get(d, key):
    """Returns d[key] or empty list if not found."""
    if d is None:
        return []
    return d.get(key, [])


@register.filter
def conflict_reasons(conflicts):
    """Returns a string of conflict reasons from a list of conflict dicts."""
    if not conflicts:
        return ""
    return " | ".join(c.get("message", "") for c in conflicts if c.get("message"))
