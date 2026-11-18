"""Filter für Listen: Suche, Auswahl und Datum.

Jeder Filter prüft den Wert aus der Adresszeile selbst. Ein ungültiger Wert wird ignoriert und nie in eine Abfrage
gegeben. Angewendet werden die Filter erst auf eine Abfrage, die die jeweilige Ansicht schon auf den Besitzer
beschränkt hat (siehe `SortFilterListMixin`): Ein Filter kann also nie fremde Daten sichtbar machen.
"""

from datetime import date

from django.db.models import Q

MAX_SEARCH_LENGTH = 100


class SearchFilter:
    """Freitext über mehrere Felder. Jedes Wort muss in mindestens einem der Felder vorkommen."""

    kind = "search"

    def __init__(self, name, label, fields):
        self.name = name
        self.label = label
        self.fields = tuple(fields)

    def get_choices(self, request):
        return []

    def default(self, request):
        return None

    def clean(self, raw, choices, request):
        value = " ".join((raw or "").split())[:MAX_SEARCH_LENGTH]
        return value or None

    def apply(self, queryset, value):
        for word in value.split():
            condition = Q()
            for field in self.fields:
                condition |= Q(**{f"{field}__icontains": word})
            queryset = queryset.filter(condition)
        return queryset


class ChoiceFilter:
    """Auswahl aus festen oder dynamischen Werten.

    `choices` ist eine Liste von (Wert, Beschriftung) oder eine Funktion `choices(request)`. `queryset_filter(queryset,
    value)` wendet einen gültigen Wert an. Mit `default` (Funktion `default(request)`) ist immer ein Wert gewählt, ohne
    gibt es die Auswahl "Alle".
    """

    kind = "select"

    def __init__(self, name, label, choices, queryset_filter, default=None):
        self.name = name
        self.label = label
        self._choices = choices
        self.queryset_filter = queryset_filter
        self._default = default

    def get_choices(self, request):
        raw = self._choices(request) if callable(self._choices) else self._choices
        return [(str(value), label) for value, label in raw]

    def default(self, request):
        return self._default(request) if self._default else None

    def clean(self, raw, choices, request):
        if raw is not None and raw in {value for value, _label in choices}:
            return raw
        return self.default(request)

    def apply(self, queryset, value):
        return self.queryset_filter(queryset, value)


class DateFilter:
    """Ein Datum (`YYYY-MM-DD`), das über `lookup` (zum Beispiel `date__gte`) auf die Abfrage wirkt."""

    kind = "date"

    def __init__(self, name, label, lookup):
        self.name = name
        self.label = label
        self.lookup = lookup

    def get_choices(self, request):
        return []

    def default(self, request):
        return None

    def clean(self, raw, choices, request):
        try:
            return date.fromisoformat((raw or "").strip()).isoformat()
        except ValueError:
            return None

    def apply(self, queryset, value):
        return queryset.filter(**{self.lookup: value})
