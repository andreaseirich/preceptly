"""Vorlagen-Tags für Listen: Sortierkopf, Seitenwechsel und Filterleiste.

    {% load list_tools %}
    {% filter_bar %}
    <table> ... {% sort_header "amount" _("Amount") %} ... </table>
    {% pagination %}

Alle Tags übernehmen die übrigen Angaben der Adresszeile (Filter, Sortierung), damit ein Klick nichts verwirft.
Die Werte stammen aus `SortFilterListMixin`, also schon geprüft; ausgegeben wird nur über `format_html` und Vorlagen.
"""

from django import template
from django.core.paginator import Paginator
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def sort_header(context, key, label, th_class=""):
    """Spaltenkopf, dessen Link nach dieser Spalte sortiert; ein zweiter Klick kehrt die Richtung um.

    `th_class` (zum Beispiel "th-right" für Beträge) kommt als Klasse an die Zelle.
    """
    request = context["request"]
    active = context.get("list_sort") == key
    direction = context.get("list_dir", "asc")
    params = request.GET.copy()
    params.pop("page", None)  # eine neue Sortierung beginnt auf Seite 1
    params["sort"] = key
    params["dir"] = "desc" if active and direction == "asc" else "asc"
    aria = ""
    mark = "↕"
    if active:
        aria = ' aria-sort="ascending"' if direction == "asc" else ' aria-sort="descending"'
        mark = "▲" if direction == "asc" else "▼"
    return format_html(
        '<th scope="col"{}{}><a class="sort-link{}" href="?{}">{}<span class="sort-mark" aria-hidden="true">{}</span></a></th>',
        format_html(' class="{}"', th_class) if th_class else "",
        mark_safe(aria),  # nur die zwei festen Werte oben
        " is-active" if active else "",
        params.urlencode(),
        label,
        mark,
    )


@register.inclusion_tag("core/list_tools/_pagination.html", takes_context=True)
def pagination(context, page_obj=None):
    """Seitenwechsel mit Seitenzahlen, "Zurück"/"Weiter" und der Angabe, welche Einträge man sieht."""
    request = context["request"]
    page = page_obj or context.get("page_obj")
    if page is None or page.paginator.count == 0:
        return {"page": None}

    def url(number):
        params = request.GET.copy()
        params["page"] = number
        return "?" + params.urlencode()

    items = []
    for number in page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1):
        if number == Paginator.ELLIPSIS:
            items.append({"ellipsis": True})
        else:
            items.append({"number": number, "url": url(number), "current": number == page.number})
    return {
        "page": page,
        "items": items,
        "prev_url": url(page.previous_page_number()) if page.has_previous() else None,
        "next_url": url(page.next_page_number()) if page.has_next() else None,
        "first": page.start_index(),
        "last": page.end_index(),
        "total": page.paginator.count,
    }


@register.inclusion_tag("core/list_tools/_filter_bar.html", takes_context=True)
def filter_bar(context):
    """Suche und Filter als GET-Formular. Die gewählte Sortierung bleibt erhalten, die Seite beginnt wieder bei 1."""
    request = context["request"]
    sort = context.get(
        "list_sort", ""
    )  # schon geprüft (Schlüssel aus sort_options), nicht der rohe Wert aus der Adresse
    direction = context.get("list_dir", "")
    reset_url = request.path + ("?" + urlencode({"sort": sort, "dir": direction}) if sort else "")
    return {
        "filters": context.get("list_filters") or [],
        "active": context.get("list_filters_active", False),
        "sort": sort,
        "direction": direction,
        "reset_url": reset_url,
    }
