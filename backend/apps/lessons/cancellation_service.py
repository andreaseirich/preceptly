"""Abgesagte Stunden ins Archiv schreiben, bevor sie gelöscht werden."""

from apps.lessons.models import CancelledSession


def archive_cancelled(sessions, cancelled_by, via) -> list[CancelledSession]:
    """Vor dem Löschen aufrufen, in derselben Transaktion.

    cancelled_by: das Django-Konto, das abgesagt hat. via: CancelledSession.VIA_*."""
    return CancelledSession.objects.bulk_create(
        [
            CancelledSession(
                contract_id=session.contract_id,
                date=session.date,
                start_time=session.start_time,
                duration_minutes=session.duration_minutes,
                notes=session.notes or "",
                was_series=bool(session.recurring_session_id),
                booked_at=session.created_at,
                booked_by_id=session.booked_by_id,
                created_via=session.created_via,
                cancelled_by=cancelled_by,
                cancelled_via=via,
            )
            for session in sessions
        ]
    )
