"""
Models for billing and invoices.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.contracts.models import Contract
from apps.lessons.models import Lesson


def _invoice_pdf_upload_to(instance, filename):
    """Per-owner path: invoices_pdf/{owner_id}/{invoice_id}/invoice.pdf."""
    return f"invoices_pdf/{instance.owner_id}/{instance.id}/invoice.pdf"


class Invoice(models.Model):
    """Invoice for billed lessons."""

    STATUS_CHOICES = [
        ("draft", _("Draft")),
        ("sent", _("Sent")),
        ("paid", _("Paid")),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
        db_index=True,
        help_text=_("Tutor who owns this invoice"),
    )
    invoice_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Sequential invoice number (Premium). INV-<id> fallback for Basic."),
    )
    payer_name = models.CharField(max_length=200, help_text=_("Name of the payer"))
    payer_address = models.TextField(blank=True, help_text=_("Address of the payer"))
    contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        help_text=_("Associated contract (optional)"),
    )
    period_start = models.DateField(help_text=_("Billing period start"))
    period_end = models.DateField(help_text=_("Billing period end"))
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", help_text=_("Invoice status")
    )
    sent_at = models.DateTimeField(null=True, blank=True, help_text=_("When marked as sent"))
    paid_at = models.DateTimeField(null=True, blank=True, help_text=_("When marked as paid"))
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Total invoice amount (may be negative if items include deductions)."),
    )
    document = models.FileField(
        upload_to="invoices/",
        null=True,
        blank=True,
        help_text=_("Generated invoice document (HTML/PDF)"),
    )
    invoice_pdf = models.FileField(
        upload_to=_invoice_pdf_upload_to,
        null=True,
        blank=True,
        help_text=_("Generated PDF document"),
    )
    invoice_pdf_created_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["period_start", "period_end"]),
            models.Index(fields=["owner", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "invoice_number"],
                condition=Q(invoice_number__isnull=False),
                name="uniq_owner_invoice_number_not_null",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="invoice_period_end_gte_start",
            ),
        ]

    def __str__(self):
        return f"Invoice {self.id} - {self.payer_name} ({self.period_start} - {self.period_end})"

    def calculate_total(self):
        """Calculates the total amount from all InvoiceItems."""
        total = sum((item.amount for item in self.items.all()), Decimal("0.00"))
        self.total_amount = total
        self.save(update_fields=["total_amount", "updated_at"])
        return total

    def delete(self, *args, **kwargs):
        """
        Overrides delete() to reset Lessons to TAUGHT and delete invoice_pdf file.

        When deleting an invoice, all associated lessons
        with status PAID are reset to TAUGHT.
        A lesson is only reset if it is not in other invoices.
        Also deletes the invoice_pdf file from storage if present.
        """
        with transaction.atomic():
            # Delete PDF file before DB delete so we have the field value
            if self.invoice_pdf:
                try:
                    self.invoice_pdf.delete(save=False)
                except Exception:  # noqa: S110 - intentional: do not block invoice deletion on file/storage errors
                    pass

            # Sammle alle Lessons dieser Rechnung (vor dem Löschen!)
            invoice_items = list(self.items.all())
            lesson_ids = [item.lesson_id for item in invoice_items if item.lesson_id]

            # Bulk-Query: Finde alle lesson_ids, die in anderen Rechnungen vorkommen
            shared_ids = set(
                InvoiceItem.objects.filter(lesson_id__in=lesson_ids)
                .exclude(invoice=self)
                .values_list("lesson_id", flat=True)
            )
            lessons_to_reset = [lid for lid in lesson_ids if lid not in shared_ids]

            # Lösche die Invoice (CASCADE löscht automatisch alle InvoiceItems)
            super().delete(*args, **kwargs)

            # Setze Lessons zurück auf TAUGHT via Bulk-Update
            from django.utils import timezone

            reset_count = Lesson.objects.filter(pk__in=lessons_to_reset, status="paid").update(
                status="taught", updated_at=timezone.now()
            )

            return reset_count


class InvoiceItem(models.Model):
    """Single invoice item (corresponds to a lesson)."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="items", help_text=_("Associated invoice")
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_items",
        help_text=_("Associated lesson (may be deleted later)"),
    )
    description = models.CharField(max_length=500, help_text=_("Item description"))
    date = models.DateField(help_text=_("Lesson date (copy)"))
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], help_text=_("Duration in minutes (copy)")
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Amount for this item (negative for deductions, e.g. a tutor no-show)."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "description"]
        verbose_name = _("Invoice Item")
        verbose_name_plural = _("Invoice Items")
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "lesson"],
                condition=Q(lesson__isnull=False),
                name="uniq_invoiceitem_invoice_lesson",
            ),
        ]

    def __str__(self):
        return f"{self.description} - {self.amount}€"
