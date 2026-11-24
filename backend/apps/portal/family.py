"""Weitere Kinder an ein bestehendes Eltern-Konto hängen."""

import uuid

from apps.portal.models import ParentStudentLink


def link_child_to_account(account, contract):
    """Verknüpft `contract` mit dem Konto `account`.

    Hat das Konto schon eine aktivierte Verknüpfung, hat der Elternteil seine E-Mail-Adresse und sein Passwort
    schon bestätigt: Das neue Kind ist sofort sichtbar, ohne zweite Aktivierung. Sonst bleibt die Verknüpfung
    inaktiv und wird freigeschaltet, sobald das Konto aktiviert wird (siehe `activate_pending_siblings`).

    Gibt zurück, ob das Kind jetzt im Portal sichtbar ist (Verknüpfung aktiv).
    """
    link, created = ParentStudentLink.objects.get_or_create(parent=account, contract=contract)
    if not created or link.is_active:
        return link.is_active
    if (
        ParentStudentLink.objects.filter(parent=account, is_active=True)
        .exclude(pk=link.pk)
        .exists()
    ):
        _activate(link)
        return True
    return False


def activate_pending_siblings(account, activated_link):
    """Schaltet die übrigen inaktiven Kinder desselben Kontos frei, wenn eine Verknüpfung aktiviert wurde."""
    for link in ParentStudentLink.objects.filter(parent=account, is_active=False).exclude(
        pk=activated_link.pk
    ):
        _activate(link)


def _activate(link):
    link.is_active = True
    link.invite_token = (
        uuid.uuid4().hex
    )  # ein offener Aktivierungslink darf das Passwort nicht überschreiben
    link.invite_token_created_at = None
    link.save(update_fields=["is_active", "invite_token", "invite_token_created_at"])
