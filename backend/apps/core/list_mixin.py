"""Baukasten für Listen: Seitenwechsel, Sortierung und Filter in einer Mischklasse.

Eine Liste (`ListView`) trägt die Mischklasse als erste Basisklasse und beschreibt ihre Spalten und Filter:

    class InvoiceListView(SortFilterListMixin, LoginRequiredMixin, ListView):
        paginate_by = 20
        sort_options = {"amount": ("total_amount",), "payer": (Lower("payer_name"),)}
        default_sort, default_dir = "created", "desc"
        list_filters = (SearchFilter("q", _("Search"), ("payer_name",)),)

Die Ansicht beschränkt ihre Abfrage in `get_queryset()` wie bisher auf den Besitzer. Die Mischklasse greift erst in
`paginate_queryset()` ein, also danach: Filter und Sortierung wirken nur auf Daten, die der Nutzer ohnehin sehen darf.

Sortierung: Der Schlüssel `?sort=` muss in `sort_options` stehen, sonst gilt die Standardsortierung. Es kommt nie ein
Wert aus der Adresszeile in `order_by`. Leere Werte stehen am Ende, am Schluss sortiert immer `pk`, damit die Seiten
bei gleichen Werten nicht durcheinandergeraten.

Seitenwechsel: tolerant. Eine ungültige oder zu große Seitenzahl führt auf die erste bzw. letzte Seite, nie zu 404.
"""

from django.db.models import F


class SortFilterListMixin:
    sort_options = {}  # Schlüssel -> Tuple aus Feldnamen oder Ausdrücken (zum Beispiel Lower("name"))
    default_sort = ""
    default_dir = "asc"
    list_filters = ()

    # Die Abfrage nach Filtern und Sortierung, aber vor dem Seitenwechsel: Summen über alle Seiten brauchen sie.
    controlled_queryset = None

    def get_list_filters(self):
        return self.list_filters

    def _filter_state(self):
        """(Filter, Auswahlmöglichkeiten, geprüfter Wert) je Filter; je Anfrage einmal berechnet."""
        if not hasattr(self, "_list_filter_state"):
            state = []
            for list_filter in self.get_list_filters():
                choices = list_filter.get_choices(self.request)
                value = list_filter.clean(
                    self.request.GET.get(list_filter.name), choices, self.request
                )
                state.append((list_filter, choices, value))
            self._list_filter_state = state
        return self._list_filter_state

    def get_sort(self):
        key = self.request.GET.get("sort", "")
        return key if key in self.sort_options else self.default_sort

    def get_dir(self):
        direction = self.request.GET.get("dir", "")
        if direction in ("asc", "desc"):
            return direction
        # Die Standardrichtung (zum Beispiel "neueste zuerst") gilt nur für die Standardspalte. Wer eine andere Spalte
        # ohne Richtung wählt, bekommt aufsteigend.
        return self.default_dir if self.get_sort() == self.default_sort else "asc"

    def _order_by(self):
        direction = self.get_dir()
        terms = []
        for field in self.sort_options[self.get_sort()]:
            expression = field if hasattr(field, "resolve_expression") else F(field)
            terms.append(
                expression.desc(nulls_last=True)
                if direction == "desc"
                else expression.asc(nulls_last=True)
            )
        terms.append("pk")
        return terms

    def apply_list_controls(self, queryset):
        for list_filter, _choices, value in self._filter_state():
            if value is not None:
                queryset = list_filter.apply(queryset, value)
        return queryset.order_by(*self._order_by())

    def paginate_queryset(self, queryset, page_size):
        queryset = self.apply_list_controls(queryset)
        self.controlled_queryset = queryset
        paginator = self.get_paginator(
            queryset,
            page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = []
        active = False
        for list_filter, choices, value in self._filter_state():
            if value is not None and value != list_filter.default(self.request):
                active = True
            filters.append(
                {
                    "name": list_filter.name,
                    "label": list_filter.label,
                    "kind": list_filter.kind,
                    "value": value or "",
                    "has_default": list_filter.default(self.request) is not None,
                    "choices": [
                        {"value": choice, "label": label, "selected": choice == value}
                        for choice, label in choices
                    ],
                }
            )
        context["list_sort"] = self.get_sort()
        context["list_dir"] = self.get_dir()
        context["list_filters"] = filters
        context["list_filters_active"] = active
        return context
