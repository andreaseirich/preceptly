"""Auswahllisten und Filter für Listen rund um Schüler und Institute (immer nur die des angemeldeten Nutzers)."""

from django.utils.translation import gettext as _

from apps.contracts.models import Contract, Institute


def student_choices(request):
    """Die eigenen Schüler als (id, Name), sortiert nach Nachname."""
    contracts = Contract.objects.filter(user=request.user).order_by("last_name", "first_name")
    return [(contract.pk, contract.full_name) for contract in contracts]


def institute_choices(request):
    """Die eigenen Institute und "Privatunterricht" (kein Institut)."""
    institutes = Institute.objects.filter(user=request.user).order_by("institute_name")
    return [("none", _("Private lessons"))] + [(i.pk, i.institute_name) for i in institutes]


def filter_by_institute(queryset, value):
    if value == "none":
        return queryset.filter(institute_fk__isnull=True)
    return queryset.filter(institute_fk_id=int(value))
