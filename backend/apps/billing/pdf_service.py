"""
Service for generating invoice PDFs.
"""

from io import BytesIO

from apps.billing.models import Invoice
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    """
    Generate PDF bytes for an invoice.

    Args:
        invoice: Invoice instance

    Returns:
        PDF file bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()

    elements = []

    # Title
    elements.append(Paragraph("Invoice", styles["Title"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Invoice number
    inv_num = invoice.invoice_number or str(invoice.id)
    elements.append(Paragraph(f"<b>Invoice Number:</b> {inv_num}", styles["Normal"]))
    elements.append(
        Paragraph(
            f"<b>Invoice Date:</b> {invoice.created_at.strftime('%d.%m.%Y')}",
            styles["Normal"],
        )
    )
    elements.append(
        Paragraph(
            f"<b>Period:</b> {invoice.period_start.strftime('%d.%m.%Y')} - {invoice.period_end.strftime('%d.%m.%Y')}",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 0.5 * cm))

    # Payer
    elements.append(Paragraph("<b>Payer</b>", styles["Heading2"]))
    elements.append(Paragraph(invoice.payer_name, styles["Normal"]))
    if invoice.payer_address:
        elements.append(Paragraph(invoice.payer_address.replace("\n", "<br/>"), styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Items table
    elements.append(Paragraph("<b>Invoice Items</b>", styles["Heading2"]))
    data = [
        ["Date", "Description", "Duration", "Amount"],
    ]
    for item in invoice.items.all():
        data.append(
            [
                item.date.strftime("%d.%m.%Y"),
                item.description,
                f"{item.duration_minutes} Min.",
                f"{item.amount:.2f} €",
            ]
        )
    data.append(["", "", "Total:", f"{invoice.total_amount:.2f} €"])

    table = Table(data, colWidths=[4 * cm, 8 * cm, 3 * cm, 3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), "#e5e7eb"),
                ("TEXTCOLOR", (0, 0), (-1, 0), "#111827"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -2), "#ffffff"),
                ("BACKGROUND", (0, -1), (-1, -1), "#f3f4f6"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, "#d1d5db"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
