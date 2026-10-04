"""Meldung an den Tutor, wenn beim Anlegen einer Serie belegte Tage ausgelassen wurden."""

from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils.translation import ngettext


def report_busy_days(request, busy):
    """Zeigt, welche Tage ausgelassen wurden, weil dort schon eine Stunde oder eine Blockzeit liegt.

    busy ist die Liste result["busy"] aus RecurringSessionService.generate_sessions(skip_busy=True)."""
    if not busy:
        return
    shown = ", ".join(entry["date"].strftime("%d.%m.%Y") for entry in busy[:10])
    if len(busy) > 10:
        shown += _(" and {more} more").format(more=len(busy) - 10)
    messages.info(
        request,
        ngettext(
            "{count} day was already busy and was left out: {days}.",
            "{count} days were already busy and were left out: {days}.",
            len(busy),
        ).format(count=len(busy), days=shown),
    )
