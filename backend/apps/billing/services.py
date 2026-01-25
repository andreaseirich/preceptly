"""
Services für Billing-Funktionalität.
"""

from decimal import Decimal

from apps.billing.models import Invoice, InvoiceItem
from apps.lessons.models import Lesson
from django.db import transaction
from django.utils.translation import gettext as _


class InvoiceService:
    """Service für Invoice-Operationen."""

    @staticmethod
    def get_billable_lessons(period_start, period_end, contract_id=None):
        """
        Gibt alle Lessons zurück, die für eine Abrechnung in Frage kommen.

        Nur Lessons mit Status TAUGHT, die noch nicht in einer Invoice sind.
        Lessons mit Status PLANNED oder PAID werden ausgeschlossen.
        Eine Lesson kann nur in einer Rechnung vorkommen.

        Args:
            period_start: Startdatum des Zeitraums
            period_end: Enddatum des Zeitraums
            contract_id: Optional: Filter nach Vertrag-ID

        Returns:
            QuerySet von Lessons mit Status TAUGHT, die noch nicht in einem InvoiceItem sind
        """
        queryset = (
            Lesson.objects.filter(
                status="taught",  # Nur unterrichtete Lessons (nicht PLANNED oder PAID)
                date__gte=period_start,
                date__lte=period_end,
            )
            .exclude(
                invoice_items__isnull=False  # Keine Lessons, die bereits in einer Rechnung sind (1:1-Beziehung)
            )
            .select_related("contract", "contract__student")
        )

        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)

        return queryset.order_by("date", "start_time")

    @staticmethod
    def create_invoice_from_lessons(period_start, period_end, contract=None):
        """
        Erstellt eine Invoice mit InvoiceItems aus allen verfügbaren Lessons im Zeitraum.

        Automatisch werden alle Lessons mit Status TAUGHT im angegebenen Zeitraum verwendet,
        die noch nicht in einer Rechnung sind.

        Args:
            period_start: Startdatum
            period_end: Enddatum
            contract: Optional: Filter nach Vertrag

        Returns:
            Invoice-Instanz
        """
        # Lade automatisch alle abrechenbaren Lessons im Zeitraum
        contract_id = contract.id if contract else None
        with transaction.atomic():
            lessons = InvoiceService.get_billable_lessons(
                period_start, period_end, contract_id
            ).select_for_update()

            if not lessons.exists():
                raise ValueError(_("No billable lessons found in the specified period."))

            if contract:
                # Use tutoring institute as payer if available, otherwise student
                if contract.institute:
                    payer_name = contract.institute
                else:
                    payer_name = contract.student.full_name
                payer_address = ""
            else:
                first_lesson = lessons.first()
                first_contract = first_lesson.contract
                # Use tutoring institute as payer if available, otherwise student
                if first_contract.institute:
                    payer_name = first_contract.institute
                else:
                    payer_name = first_contract.student.full_name
                payer_address = ""

            invoice = Invoice.objects.create(
                payer_name=payer_name,
                payer_address=payer_address,
                contract=contract or lessons.first().contract,
                period_start=period_start,
                period_end=period_end,
                status="draft",
            )

            total_amount = Decimal("0.00")
            for lesson in lessons:
                contract = lesson.contract
                unit_duration = Decimal(str(contract.unit_duration_minutes))
                lesson_duration = Decimal(str(lesson.duration_minutes))
                units = lesson_duration / unit_duration
                rate_per_unit = contract.hourly_rate
                amount = units * rate_per_unit

                InvoiceItem.objects.create(
                    invoice=invoice,
                    lesson=lesson,
                    description=_("Lesson {date} {time} - {student}").format(
                        date=lesson.date,
                        time=lesson.start_time.strftime("%H:%M"),
                        student=lesson.contract.student.full_name,
                    ),
                    date=lesson.date,
                    duration_minutes=lesson.duration_minutes,
                    amount=amount,
                )

                total_amount += amount

                lesson.status = "paid"
                lesson.save(update_fields=["status", "updated_at"])

            invoice.total_amount = total_amount
            invoice.save(update_fields=["total_amount", "updated_at"])

            return invoice

    @staticmethod
    def delete_invoice(invoice: Invoice):
        """
        Deletes an invoice and resets lessons to TAUGHT.

        The logic for resetting lesson status is implemented in the delete() method
        of the Invoice model, so it is always executed,
        even if invoice.delete() is called directly.

        Args:
            invoice: The invoice to delete

        Returns:
            Number of reset lessons
        """
        # The delete() method of the Invoice model automatically resets all
        # lessons to TAUGHT and returns the count
        reset_count = invoice.delete()
        return reset_count
