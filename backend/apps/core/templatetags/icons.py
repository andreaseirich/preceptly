"""Template-Tags für die Icons: {% icon "users" %} und einmal je Seite {% icon_sprite %}.

Die Zeichnung steht nur einmal im Sprite; jedes {% icon %} verweist darauf. Icons sind Dekor (aria-hidden): Der Name der Schaltfläche steht
daneben als Text oder als aria-label am Knopf.
"""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core.icon_paths import ICON_PATHS

register = template.Library()


@register.simple_tag
def icon(name, css_class=""):
    """Ein Icon aus dem Sprite. Unbekannte Namen ergeben nichts (der Test test_icons fängt sie vorher ab)."""
    if name not in ICON_PATHS:
        return ""
    classes = f"icon {css_class}".strip()
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="#i-{}"></use></svg>',
        classes,
        name,
    )


@register.simple_tag
def icon_sprite():
    """Alle Zeichnungen als unsichtbares SVG; steht einmal direkt hinter <body>."""
    symbols = "".join(
        f'<symbol id="i-{name}" viewBox="0 0 24 24">{paths}</symbol>'
        for name, paths in ICON_PATHS.items()
    )
    return mark_safe(
        f'<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">{symbols}</svg>'
    )  # noqa: S308 - feste Konstanten
