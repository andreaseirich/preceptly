"""
Helper to resolve Invoice owner from contract/items. Used by migrations and tests.
"""

from django.core.exceptions import ObjectDoesNotExist


def resolve_invoice_owner(invoice):
    """
    Determine the owner (User) for an Invoice.

    Priority:
    a) If invoice.contract exists: owner = contract.user
    b) Else: owner from first item's lesson.contract.user (by item id)

    Returns:
        User instance or None if not determinable.

    Raises:
        ValueError: If invoice has no contract and no items with determinable owner.
    """
    if invoice.contract_id:
        try:
            return invoice.contract.user
        except ObjectDoesNotExist:
            return None

    first_item = (
        invoice.items.select_related("lesson__contract__user")
        .filter(lesson__isnull=False)
        .order_by("id")
        .first()
    )
    if first_item and first_item.lesson_id and first_item.lesson.contract_id:
        try:
            return first_item.lesson.contract.user
        except ObjectDoesNotExist:
            return None

    return None
