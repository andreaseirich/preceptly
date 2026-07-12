"""
Services für Billing-Funktionalität.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.billing.forms import NO_INSTITUTE_FILTER_VALUE
from apps.billing.models import Invoice, InvoiceItem
from apps.contracts.institute_billing import (
    calculate_lesson_amount,
    resolve_institute_billing_config,
)
from apps.core.feature_flags import Feature, user_has_feature
from apps.lessons.models import Lesson

logger = logging.getLogger(__name__)


class InvoiceService:
    """Service für Invoice-Operationen."""

    @staticmethod
    def get_billable_lessons(period_start, period_end, contract_id=None, institute=None, user=None):
        """
        Gibt alle Lessons zurück, die für eine Abrechnung in Frage kommen.

        Nur Lessons mit Status TAUGHT, die noch nicht in einer Invoice sind.
        Lessons mit Status PLANNED oder PAID werden ausgeschlossen.
        Eine Lesson kann nur in einer Rechnung vorkommen.

        Args:
            period_start: Startdatum des Zeitraums
            period_end: Enddatum des Zeitraums
            contract_id: Optional: Filter nach Vertrag-ID
            institute: Optional: Filter nach Institut (Contract.institute)
            user: Optional: Filter nach Tutor (contract__user)

        Returns:
            QuerySet von Lessons mit Status TAUGHT, die noch nicht in einem InvoiceItem sind

        Raises:
            ValidationError: Wenn period_start nach period_end liegt oder der Zeitraum > 1 Jahr ist
        """
        from django.core.exceptions import ValidationError

        if period_start > period_end:
            raise ValidationError("period_start muss vor period_end liegen.")
        if (period_end - period_start).days > 366:
            raise ValidationError("Zeitraum darf maximal 1 Jahr betragen.")

        queryset = (
            Lesson.objects.filter(
                status="taught",  # Nur unterrichtete Lessons (nicht PLANNED oder PAID)
                date__gte=period_start,
                date__lte=period_end,
            )
            .exclude(
                invoice_items__isnull=False  # Keine Lessons, die bereits in einer Rechnung sind (1:1-Beziehung)
            )
            .select_related("contract")
        )

        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)
        if institute == NO_INSTITUTE_FILTER_VALUE:
            queryset = queryset.filter(
                Q(contract__institute__isnull=True) | Q(contract__institute="")
            )
        elif institute:
            queryset = queryset.filter(contract__institute=institute)
        if user:
            queryset = queryset.filter(contract__user=user)

        return queryset.order_by("date", "start_time")

    @staticmethod
    def create_invoice_from_lessons(
        period_start, period_end, contract=None, institute=None, user=None
    ):
        """
        Erstellt eine Invoice mit InvoiceItems aus allen verfügbaren Lessons im Zeitraum.

        Automatisch werden alle Lessons mit Status TAUGHT im angegebenen Zeitraum verwendet,
        die noch nicht in einer Rechnung sind.

        Args:
            period_start: Startdatum
            period_end: Enddatum
            contract: Optional: Filter nach Vertrag
            institute: Optional: Filter nach Institut
            user: Optional: Filter nach Tutor

        Returns:
            Invoice-Instanz

        Raises:
            ValidationError: Wenn der Zeitraum ungültig ist
            ValueError: Wenn keine abrechenbaren Lessons gefunden werden
        """
        from django.core.exceptions import ValidationError
        from django.db.models import F

        if period_start > period_end:
            raise ValidationError("period_start muss vor period_end liegen.")
        if (period_end - period_start).days > 366:
            raise ValidationError("Zeitraum darf maximal 1 Jahr betragen.")

        contract_id = contract.id if contract else None
        logger.info(
            "Creating invoice: period=%s-%s, user=%s, contract=%s",
            period_start,
            period_end,
            user,
            contract,
        )
        with transaction.atomic():
            lesson_list = list(
                InvoiceService.get_billable_lessons(
                    period_start, period_end, contract_id, institute=institute, user=user
                ).select_for_update()
            )

            if not lesson_list:
                raise ValueError(_("No billable lessons found in the specified period."))

            first_lesson = lesson_list[0]
            owner = user if user is not None else first_lesson.contract.user

            if contract:
                if contract.institute:
                    payer_name = contract.institute
                else:
                    payer_name = contract.full_name
                payer_address = ""
            else:
                first_contract = first_lesson.contract
                if first_contract.institute:
                    payer_name = first_contract.institute
                else:
                    payer_name = first_contract.full_name
                payer_address = ""

            invoice_kwargs = {
                "owner": owner,
                "payer_name": payer_name,
                "payer_address": payer_address,
                "contract": contract or first_lesson.contract,
                "period_start": period_start,
                "period_end": period_end,
                "status": "draft",
            }

            if user and user_has_feature(user, Feature.FEATURE_BILLING_PRO):
                from apps.core.models import UserProfile

                with transaction.atomic():
                    profile, _created = UserProfile.objects.select_for_update().get_or_create(
                        user=user,
                        defaults={"next_invoice_number": 1},
                    )
                    invoice_number = profile.next_invoice_number
                    UserProfile.objects.filter(pk=profile.pk).update(
                        next_invoice_number=F("next_invoice_number") + 1
                    )
                invoice_kwargs["invoice_number"] = f"INV-{invoice_number:04d}"
            else:
                invoice_kwargs["invoice_number"] = None

            invoice = Invoice.objects.create(**invoice_kwargs)

            total_amount = Decimal("0.00")
            institute_config_cache = {}
            for lesson in lesson_list:
                lesson_contract = lesson.contract
                cache_key = (owner.pk, (lesson_contract.institute or "").strip().lower())
                if cache_key not in institute_config_cache:
                    institute_config_cache[cache_key] = resolve_institute_billing_config(
                        owner, lesson_contract.institute
                    )
                institute_config = institute_config_cache[cache_key]
                has_tiers = bool(institute_config and institute_config.tiers)
                unpaid_on_no_show = bool(
                    institute_config and institute_config.unpaid_on_tutor_no_show
                )

                try:
                    amount = calculate_lesson_amount(lesson, owner, config=institute_config)
                except (ValueError, ZeroDivisionError) as e:
                    logger.error("Amount calc failed for lesson %s: %s", lesson.pk, e)
                    raise

                desc = _("Lesson {date} {time} - {student}").format(
                    date=lesson.date,
                    time=lesson.start_time.strftime("%H:%M"),
                    student=lesson.contract.full_name,
                )
                if getattr(lesson, "tutor_no_show", False):
                    if has_tiers:
                        desc = f"{desc} ({_('tutor no-show / deduction')})"
                    elif unpaid_on_no_show:
                        desc = f"{desc} ({_('not billed — tutor no-show')})"

                from django.db import IntegrityError

                try:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        lesson=lesson,
                        description=desc,
                        date=lesson.date,
                        duration_minutes=lesson.duration_minutes,
                        amount=amount,
                    )
                except IntegrityError as e:
                    logger.error("Duplicate InvoiceItem for lesson %s: %s", lesson.pk, e)
                    raise ValueError(f"Lesson {lesson.pk} already invoiced") from e

                total_amount += amount

                lesson.status = "paid"
                lesson.save(update_fields=["status", "updated_at"])

            invoice.total_amount = total_amount
            invoice.save(update_fields=["total_amount", "updated_at"])

            return invoice

    @staticmethod
    def delete_invoice(invoice: Invoice) -> int:
        """
        Deletes an invoice and resets lessons to TAUGHT.

        The logic for resetting lesson status is implemented in the delete() method
        of the Invoice model, so it is always executed,
        even if invoice.delete() is called directly.

        Args:
            invoice: The invoice to delete

        Returns:
            Number of reset lessons (int). Returns 0 if the model's delete()
            does not return an integer count.
        """
        result = invoice.delete()
        # invoice.delete() ist überschrieben und gibt int zurück (Anzahl zurückgesetzter Lessons)
        return result if isinstance(result, int) else 0

    @staticmethod
    def mark_invoice_as_sent(invoice: Invoice) -> None:
        """Mark invoice as sent. Sets status=sent, sent_at=now."""
        invoice.status = "sent"
        invoice.sent_at = timezone.now()
        invoice.save(update_fields=["status", "sent_at", "updated_at"])

    @staticmethod
    def mark_invoice_as_paid(invoice: Invoice, paid_at=None) -> None:
        """Mark invoice as paid. Sets status=paid, paid_at. Updates lessons: a lesson is
        paid only if ALL invoices containing it have status=paid."""
        with transaction.atomic():
            from datetime import datetime
            from datetime import time as dt_time

            invoice.status = "paid"
            if paid_at is not None:
                invoice.paid_at = timezone.make_aware(datetime.combine(paid_at, dt_time.min))
            else:
                invoice.paid_at = timezone.now()
            invoice.save(update_fields=["status", "paid_at", "updated_at"])
            PaymentService.recompute_lesson_paid_for_invoice_items(invoice)

    @staticmethod
    def undo_invoice_paid(invoice: Invoice) -> None:
        """Undo paid: set status to sent (or draft if never sent), clear paid_at.
        Recomputes lesson paid flags for affected lessons."""
        with transaction.atomic():
            invoice.status = "sent" if invoice.sent_at else "draft"
            invoice.paid_at = None
            invoice.save(update_fields=["status", "paid_at", "updated_at"])
            PaymentService.recompute_lesson_paid_for_invoice_items(invoice)


class PaymentService:
    """Recompute lesson paid status based on invoice states."""

    @staticmethod
    def recompute_lesson_paid_for_invoice_items(invoice: Invoice) -> None:
        """For each lesson in this invoice's items, set paid iff all invoices
        containing that lesson have status=paid.

        Verwendet eine effiziente Bulk-Query statt N+1-Schleifen.
        """
        lesson_ids = list(
            invoice.items.filter(lesson__isnull=False).values_list("lesson_id", flat=True)
        )

        if not lesson_ids:
            return

        unpaid_lesson_ids = set(
            InvoiceItem.objects.filter(lesson_id__in=lesson_ids)
            .exclude(invoice__status="paid")
            .values_list("lesson_id", flat=True)
        )
        paid_ids = set(lesson_ids) - unpaid_lesson_ids

        with transaction.atomic():
            if unpaid_lesson_ids:
                Lesson.objects.filter(id__in=unpaid_lesson_ids).update(status="taught")
            if paid_ids:
                Lesson.objects.filter(id__in=paid_ids).update(status="paid")
