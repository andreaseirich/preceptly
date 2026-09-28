"""Weiche Grenzen des Free-Tarifs: ein Hinweis mit Upgrade-Link, gespeichert
wird trotzdem. Hart durchgesetzt werden nur die Grenzen, die die Preisseite
nennt (feature_flags.py).

Ein Schüler ist ein Vertrag - angelegt über die Schüler-Ansicht oder über
„Vertrag anlegen“. Beide Wege rufen warn_if_student_limit_reached() auf; bis
27.09.2026 kannte nur der erste den Hinweis (Prüfbericht F3).
"""

from django.contrib import messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

from apps.core.feature_flags import FREE_STUDENT_LIMIT, is_new_free_user


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
                "Free plan: the limit of 5 active students has been reached. "
                'Your student was saved — <a href="{}">upgrade to a paid plan</a> for unlimited students.'
            ),
            reverse("core:landing") + "#pricing",
        ),
    )
