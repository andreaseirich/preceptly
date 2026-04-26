"""
Service for invoice document generation.
"""

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from apps.billing.models import Invoice


class InvoiceDocumentService:
    """Service for generating invoice documents."""

    @staticmethod
    def generate_html_document(invoice: Invoice) -> str:
        """
        Generates an HTML document for an invoice.

        Args:
            invoice: Invoice instance

        Returns:
            HTML string
        """
        context = {
            "invoice": invoice,
            "items": invoice.items.all(),
        }

        html = render_to_string("billing/invoice_document.html", context)
        return html

    @staticmethod
    def save_document(invoice: Invoice) -> str:
        """
        Generates and saves the invoice document.

        Args:
            invoice: Invoice instance

        Returns:
            Path to the saved document
        """
        html_content = InvoiceDocumentService.generate_html_document(invoice)

        # Create filename
        filename = f"invoice_{invoice.id}_{invoice.period_start}_{invoice.period_end}.html"

        # Save as FileField
        invoice.document.save(filename, ContentFile(html_content.encode("utf-8")), save=True)

        return invoice.document.path
