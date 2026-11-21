"""Weiche Grenzen des Free-Tarifs: ein Hinweis mit Upgrade-Link, gespeichert
wird trotzdem. Hart durchgesetzt werden nur die Grenzen, die die Preisseite
nennt (feature_flags.py).

Ein Schüler ist ein Vertrag - angelegt über die Schüler-Ansicht oder über
„Vertrag anlegen“. Beide Wege rufen warn_if_student_limit_reached() auf; bis
27.09.2026 kannte nur der erste den Hinweis (Prüfbericht F3).
"""

from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext as _

from apps.core.feature_flags import FREE_STUDENT_LIMIT, is_new_free_user


def invoices_created_this_month(user) -> int:
    """Rechnungen des Kontos, die im laufenden Kalendermonat angelegt wurden (deutsche Zeit, wie die Anzeige).

    Es zählt der Zeitpunkt des Anlegens, nicht der Zeitraum der Stunden. Stornorechnungen sind eigene Rechnungen und zählen mit; wer eine
    Rechnung aus dem Vormonat storniert, belegt also eine Rechnung im laufenden Monat. Früher wurde der Monat aus UTC gelesen, die Abfrage
    aber in deutscher Zeit ausgewertet: In der ersten Stunde eines Monats zählte sie dadurch falsch (der Hinweis blieb aus).
    """
    from apps.billing.models import Invoice

    now = timezone.localtime()
    return Invoice.objects.filter(
        owner=user, created_at__year=now.year, created_at__month=now.month
    ).count()


def warn_if_student_limit_reached(request) -> None:
    """Vor dem Speichern eines neuen Schülers aufrufen."""
    from apps.contracts.models import Contract

    if not is_new_free_user(request.user):
        return
    if Contract.objects.filter(user=request.user).count() < FREE_STUDENT_LIMIT:
        return
    messages.warning(
        request,
        format_html(
            _(
                "Free plan: the limit of 5 students has been reached. "
                'Your student was saved — <a href="{}">upgrade to a paid plan</a> for unlimited students.'
            ),
            reverse("core:landing") + "#pricing",
        ),
    )
