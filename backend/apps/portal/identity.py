"""Eindeutigkeit der E-Mail-Adressen, mit denen man sich im Portal anmeldet.

Ein Portal-Login wird auf zwei Wegen gefunden (siehe ``PortalLoginView``):
über die E-Mail des Django-Users oder — als Rückfall für Alt-Zugänge — über
die Vertrags-E-Mail eines ``StudentPortalLink``. Beide Wege müssen eindeutig
bleiben, sonst verdeckt ein Konto das andere und der Betroffene kommt nicht
mehr in sein Portal.
"""

from django.contrib.auth import get_user_model

from apps.portal.models import StudentPortalLink


def portal_login_conflict(email, *, exclude_user_pk=None, exclude_contract_pk=None) -> bool:
    """True, wenn sich mit dieser E-Mail bereits ein anderer Zugang anmelden kann."""
    email = (email or "").strip()
    if not email:
        return False

    users = get_user_model().objects.filter(email__iexact=email, portal_profile__isnull=False)
    if exclude_user_pk is not None:
        users = users.exclude(pk=exclude_user_pk)
    if users.exists():
        return True

    links = StudentPortalLink.objects.filter(contract__email__iexact=email)
    if exclude_contract_pk is not None:
        links = links.exclude(contract_id=exclude_contract_pk)
    return links.exists()
