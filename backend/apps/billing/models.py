"""
Models for billing and invoices.
"""

from decimal import Decimal

from apps.contracts.models import Contract
from apps.lessons.models import Lesson
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


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
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text=_("Total invoice amount"),
    )
    document = models.FileField(
        upload_to="invoices/",
        null=True,
        blank=True,
        help_text=_("Generated invoice document (HTML/PDF)"),
    )
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
        ]

    def __str__(self):
        return f"Invoice {self.id} - {self.payer_name} ({self.period_start} - {self.period_end})"

    def calculate_total(self):
        """Calculates the total amount from all InvoiceItems."""
        total = sum(item.amount for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=["total_amount", "updated_at"])
        return total

    def delete(self, *args, **kwargs):
        """
        Overrides delete() to reset Lessons to TAUGHT.

        When deleting an invoice, all associated lessons
        with status PAID are reset to TAUGHT.
        A lesson is only reset if it is not in other invoices.
        """
        # Sammle alle Lessons dieser Rechnung (vor dem Löschen!)
        invoice_items = list(self.items.all())
        lesson_ids = [item.lesson_id for item in invoice_items if item.lesson_id]

        # Prüfe für jede Lesson, ob sie in anderen Rechnungen ist (vor dem Löschen!)
        lessons_to_reset = []
        for lesson_id in lesson_ids:
            if not lesson_id:
                continue

            # Prüfe, ob Lesson in anderen Rechnungen ist
            other_invoice_items = InvoiceItem.objects.filter(lesson_id=lesson_id).exclude(
                invoice=self
            )

            # Nur zurücksetzen, wenn Lesson nicht in anderen Rechnungen ist
            if not other_invoice_items.exists():
                lessons_to_reset.append(lesson_id)

        # Lösche die Invoice (CASCADE löscht automatisch alle InvoiceItems)
        super().delete(*args, **kwargs)

        # Setze Lessons zurück auf TAUGHT
        from apps.lessons.models import Lesson

        reset_count = 0
        for lesson_id in lessons_to_reset:
            lesson = Lesson.objects.filter(pk=lesson_id).first()
            if lesson and lesson.status == "paid":
                lesson.status = "taught"
                lesson.save(update_fields=["status", "updated_at"])
                reset_count += 1

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
    duration_minutes = models.PositiveIntegerField(help_text=_("Duration in minutes (copy)"))
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text=_("Amount for this item"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "description"]
        verbose_name = _("Invoice Item")
        verbose_name_plural = _("Invoice Items")

    def __str__(self):
        return f"{self.description} - {self.amount}€"
