"""
Helper to resolve Invoice owner from contract/items. Used by migrations and tests.
"""


def resolve_invoice_owner(invoice):
    """
    Determine the owner (User) for an Invoice.

    Priority:
    a) If invoice.contract exists: owner = contract.student.user
    b) Else: owner from first item's lesson.contract.student.user (by item id)

    Returns:
        User instance or None if not determinable.

    Raises:
        ValueError: If invoice has no contract and no items with determinable owner.
    """
    if invoice.contract_id:
        return invoice.contract.student.user

    first_item = (
        invoice.items.select_related("lesson__contract__student__user")
        .filter(lesson__isnull=False)
        .order_by("id")
        .first()
    )
    if first_item and first_item.lesson_id and first_item.lesson.contract_id:
        return first_item.lesson.contract.student.user

    return None
