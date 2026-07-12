"""
Service for generating invoice PDFs.
"""

import html
import logging as _logging
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.billing.models import Invoice

_pdf_logger = _logging.getLogger(__name__)

_LABELS = {
    "de": {
        "title": "Rechnung",
        "issuer": "Aussteller",
        "invoice_number": "Rechnungsnummer",
        "invoice_date": "Rechnungsdatum",
        "period": "Abrechnungszeitraum",
        "recipient": "Rechnungsempfänger",
        "date_col": "Datum",
        "description_col": "Beschreibung",
        "duration_col": "Dauer",
        "amount_col": "Betrag",
        "total": "Gesamt",
        "iban": "IBAN",
        "bic": "BIC",
        "tax_number": "Steuernummer",
        "contact": "Kontakt",
        "address": "Adresse",
        "min": "Min.",
        "no_profile_warning": (
            "Hinweis: Deine Rechnungsdaten sind noch nicht vollständig. "
            "Bitte pflege sie unter Einstellungen → Rechnungsdaten."
        ),
        "payment_info": "Zahlungsinformationen",
        "bank_name": "Kontoinhaber",
        "kleinunternehmer_notice": ("Gemäß §19 Abs. 1 UStG wird keine Umsatzsteuer berechnet."),
        "pay_request": "Bitte überweisen Sie den Gesamtbetrag von {amount} auf folgendes Konto:",
    },
    "en": {
        "title": "Invoice",
        "issuer": "Issuer",
        "invoice_number": "Invoice Number",
        "invoice_date": "Invoice Date",
        "period": "Billing Period",
        "recipient": "Bill To",
        "date_col": "Date",
        "description_col": "Description",
        "duration_col": "Duration",
        "amount_col": "Amount",
        "total": "Total",
        "iban": "IBAN",
        "bic": "BIC",
        "tax_number": "Tax Number",
        "contact": "Contact",
        "address": "Address",
        "min": "min",
        "no_profile_warning": (
            "Note: Your billing profile is incomplete. "
            "Please fill it in under Settings → Invoice Details."
        ),
        "payment_info": "Payment Information",
        "bank_name": "Account Holder",
        "kleinunternehmer_notice": (
            "No VAT is charged in accordance with §19 para. 1 UStG (Kleinunternehmerregelung)."
        ),
        "pay_request": "Please transfer the total amount of {amount} to the following account:",
    },
}

_COLOR_DARK = colors.HexColor("#1e293b")
_COLOR_ACCENT = colors.HexColor("#0d8069")
_COLOR_LIGHT_BG = colors.HexColor("#f8fafc")
_COLOR_BORDER = colors.HexColor("#e2e8f0")
_COLOR_HEADER_BG = colors.HexColor("#1e293b")
_COLOR_HEADER_TEXT = colors.white
_COLOR_TOTAL_BG = colors.HexColor("#e6f4f1")
_COLOR_WARNING = colors.HexColor("#92400e")
_COLOR_WARNING_BG = colors.HexColor("#fef3c7")
_COLOR_MUTED = colors.HexColor("#64748b")


def _get_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "InvTitle",
            parent=base["Normal"],
            fontSize=26,
            fontName="Helvetica-Bold",
            textColor=_COLOR_DARK,
            leading=30,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "InvSubtitle",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=_COLOR_MUTED,
            leading=14,
        ),
        "issuer_name": ParagraphStyle(
            "InvIssuerName",
            parent=base["Normal"],
            fontSize=13,
            fontName="Helvetica-Bold",
            textColor=_COLOR_DARK,
            leading=17,
        ),
        "issuer_detail": ParagraphStyle(
            "InvIssuerDetail",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=_COLOR_MUTED,
            leading=13,
        ),
        "meta_label": ParagraphStyle(
            "InvMetaLabel",
            parent=base["Normal"],
            fontSize=8,
            fontName="Helvetica-Bold",
            textColor=_COLOR_MUTED,
            leading=12,
            spaceAfter=1,
        ),
        "meta_value": ParagraphStyle(
            "InvMetaValue",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=_COLOR_DARK,
            leading=14,
            spaceAfter=6,
        ),
        "section_heading": ParagraphStyle(
            "InvSectionHeading",
            parent=base["Normal"],
            fontSize=8,
            fontName="Helvetica-Bold",
            textColor=_COLOR_MUTED,
            leading=12,
            spaceBefore=4,
            spaceAfter=3,
            textTransform="uppercase",
        ),
        "recipient_name": ParagraphStyle(
            "InvRecipientName",
            parent=base["Normal"],
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=_COLOR_DARK,
            leading=15,
        ),
        "recipient_detail": ParagraphStyle(
            "InvRecipientDetail",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=_COLOR_DARK,
            leading=14,
        ),
        "footer": ParagraphStyle(
            "InvFooter",
            parent=base["Normal"],
            fontSize=8,
            fontName="Helvetica",
            textColor=_COLOR_MUTED,
            leading=12,
        ),
        "warning": ParagraphStyle(
            "InvWarning",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=_COLOR_WARNING,
            leading=13,
            leftIndent=8,
            rightIndent=8,
        ),
        "table_cell": ParagraphStyle(
            "InvCell",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=_COLOR_DARK,
            leading=13,
        ),
    }


def generate_invoice_pdf(invoice: Invoice, language: str = "de") -> bytes:
    """
    Generate a professional PDF for an invoice.

    Args:
        invoice: Invoice instance
        language: Language code ('de' or 'en'). Defaults to 'de'.

    Returns:
        PDF file bytes
    """
    lang = language[:2].lower() if language else "de"
    if lang not in _LABELS:
        lang = "de"
    L = _LABELS[lang]

    buffer = BytesIO()
    try:
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2.5 * cm,
        )
        styles = _get_styles()
        page_width = A4[0] - 4 * cm

        elements = []

        # ── Billing profile from owner ─────────────────────────────────────
        profile = None
        try:
            profile = invoice.owner.profile
        except Exception:  # noqa: BLE001
            _pdf_logger.debug("Could not load profile for invoice %s", invoice.pk)

        issuer_name = (profile.billing_name if profile and profile.billing_name else "") or ""
        issuer_address = (
            profile.billing_address if profile and profile.billing_address else ""
        ) or ""
        issuer_tax = (
            profile.billing_tax_number if profile and profile.billing_tax_number else ""
        ) or ""
        issuer_email = (profile.billing_email if profile and profile.billing_email else "") or ""
        issuer_phone = (profile.billing_phone if profile and profile.billing_phone else "") or ""
        issuer_website = (
            profile.billing_website if profile and profile.billing_website else ""
        ) or ""
        issuer_iban = (
            profile.billing_bank_iban if profile and profile.billing_bank_iban else ""
        ) or ""
        issuer_bic = (
            profile.billing_bank_bic if profile and profile.billing_bank_bic else ""
        ) or ""
        kleinunternehmer = bool(profile and profile.billing_kleinunternehmer)

        profile_incomplete = not issuer_name

        # ── Warning banner if profile is empty ────────────────────────────
        if profile_incomplete:
            warn_table = Table(
                [[Paragraph(L["no_profile_warning"], styles["warning"])]],
                colWidths=[page_width],
            )
            warn_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), _COLOR_WARNING_BG),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("ROUNDEDCORNERS", [4]),
                    ]
                )
            )
            elements.append(warn_table)
            elements.append(Spacer(1, 0.5 * cm))

        # ── Header: Invoice title (left) + Invoice meta (right) ───────────
        inv_num = html.escape(str(invoice.invoice_number or invoice.id))
        inv_date = invoice.created_at.strftime("%d.%m.%Y")
        period_str = (
            f"{invoice.period_start.strftime('%d.%m.%Y')} – "
            f"{invoice.period_end.strftime('%d.%m.%Y')}"
        )

        meta_left = [
            Paragraph(L["title"], styles["title"]),
        ]

        meta_right = [
            Paragraph(L["invoice_number"].upper(), styles["meta_label"]),
            Paragraph(inv_num, styles["meta_value"]),
            Paragraph(L["invoice_date"].upper(), styles["meta_label"]),
            Paragraph(inv_date, styles["meta_value"]),
            Paragraph(L["period"].upper(), styles["meta_label"]),
            Paragraph(period_str, styles["meta_value"]),
        ]

        header_table = Table(
            [[meta_left, meta_right]],
            colWidths=[page_width * 0.55, page_width * 0.45],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(header_table)
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(
            HRFlowable(width=page_width, thickness=2, color=_COLOR_ACCENT, spaceAfter=0.6 * cm)
        )

        # ── Issuer + Recipient two-column block ───────────────────────────
        issuer_block = [Paragraph(L["issuer"].upper(), styles["section_heading"])]
        if issuer_name:
            issuer_block.append(Paragraph(html.escape(issuer_name), styles["issuer_name"]))
        if issuer_address:
            for line in issuer_address.splitlines():
                if line.strip():
                    issuer_block.append(
                        Paragraph(html.escape(line.strip()), styles["issuer_detail"])
                    )
        if issuer_tax:
            issuer_block.append(
                Paragraph(f"{L['tax_number']}: {html.escape(issuer_tax)}", styles["issuer_detail"])
            )
        contact_parts = [p for p in [issuer_email, issuer_phone, issuer_website] if p]
        if contact_parts:
            issuer_block.append(
                Paragraph(
                    "  ·  ".join(html.escape(p) for p in contact_parts), styles["issuer_detail"]
                )
            )

        recipient_block = [Paragraph(L["recipient"].upper(), styles["section_heading"])]
        recipient_block.append(Paragraph(html.escape(invoice.payer_name), styles["recipient_name"]))
        if invoice.payer_address:
            for line in invoice.payer_address.splitlines():
                if line.strip():
                    recipient_block.append(
                        Paragraph(html.escape(line.strip()), styles["recipient_detail"])
                    )

        two_col = Table(
            [[issuer_block, recipient_block]],
            colWidths=[page_width * 0.5, page_width * 0.5],
        )
        two_col.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("LEFTPADDING", (1, 0), (1, 0), 20),
                ]
            )
        )
        elements.append(two_col)
        elements.append(Spacer(1, 0.7 * cm))
        elements.append(
            HRFlowable(width=page_width, thickness=0.5, color=_COLOR_BORDER, spaceAfter=0.5 * cm)
        )

        # ── Items table ───────────────────────────────────────────────────
        header_style = ParagraphStyle(
            "TblHdr",
            parent=styles["table_cell"],
            fontName="Helvetica-Bold",
            textColor=_COLOR_HEADER_TEXT,
            fontSize=9,
        )
        data = [
            [
                Paragraph(L["date_col"], header_style),
                Paragraph(L["description_col"], header_style),
                Paragraph(L["duration_col"], header_style),
                Paragraph(L["amount_col"], header_style),
            ]
        ]

        for item in invoice.items.all():
            data.append(
                [
                    Paragraph(item.date.strftime("%d.%m.%Y"), styles["table_cell"]),
                    Paragraph(html.escape(str(item.description)), styles["table_cell"]),
                    Paragraph(f"{item.duration_minutes} {L['min']}", styles["table_cell"]),
                    Paragraph(f"{item.amount:.2f} €", styles["table_cell"]),
                ]
            )

        # Total row
        total_label_style = ParagraphStyle(
            "TblTotal",
            parent=styles["table_cell"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=_COLOR_ACCENT,
        )
        data.append(
            [
                Paragraph("", styles["table_cell"]),
                Paragraph("", styles["table_cell"]),
                Paragraph(L["total"], total_label_style),
                Paragraph(f"<b>{invoice.total_amount:.2f} €</b>", total_label_style),
            ]
        )

        col_widths = [3 * cm, page_width - 3 * cm - 3 * cm - 3.5 * cm, 3 * cm, 3.5 * cm]
        table = Table(data, colWidths=col_widths, repeatRows=1)

        n_data = len(data)
        table.setStyle(
            TableStyle(
                [
                    # Header row
                    ("BACKGROUND", (0, 0), (-1, 0), _COLOR_HEADER_BG),
                    ("TEXTCOLOR", (0, 0), (-1, 0), _COLOR_HEADER_TEXT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, n_data - 2), [colors.white, _COLOR_LIGHT_BG]),
                    # Total row
                    ("BACKGROUND", (0, -1), (-1, -1), _COLOR_TOTAL_BG),
                    # Alignment
                    ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                    ("ALIGN", (2, -1), (2, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # Padding
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 1), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    # Grid lines (data rows only, no header top/bottom)
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, _COLOR_BORDER),
                    ("LINEBELOW", (0, -1), (-1, -1), 0, _COLOR_BORDER),
                    # Bold total
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, -1), (-1, -1), 11),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 0.8 * cm))

        # ── §19 UStG notice ───────────────────────────────────────────────
        if kleinunternehmer:
            notice_style = ParagraphStyle(
                "Notice19",
                parent=styles["footer"],
                fontSize=9,
                fontName="Helvetica-Oblique",
                textColor=_COLOR_MUTED,
                leading=13,
            )
            elements.append(Spacer(1, 0.3 * cm))
            elements.append(Paragraph(L["kleinunternehmer_notice"], notice_style))

        # ── Payment block ─────────────────────────────────────────────────
        if issuer_iban or issuer_bic:
            elements.append(Spacer(1, 0.6 * cm))

            # Header bar (dark background, white text)
            pay_head_style = ParagraphStyle(
                "PayHead",
                parent=styles["section_heading"],
                fontSize=9,
                textColor=colors.white,
                spaceBefore=0,
                spaceAfter=0,
            )
            pay_request_style = ParagraphStyle(
                "PayReq",
                parent=styles["meta_value"],
                fontSize=9,
                fontName="Helvetica-Bold",
                textColor=_COLOR_DARK,
                spaceAfter=0,
                leading=14,
            )
            pay_label_style = ParagraphStyle(
                "PayLbl",
                parent=styles["footer"],
                fontName="Helvetica-Bold",
                textColor=_COLOR_DARK,
                fontSize=9,
            )
            pay_val_style = ParagraphStyle(
                "PayVal2",
                parent=styles["footer"],
                textColor=_COLOR_DARK,
                fontSize=9,
            )
            pay_total_label = ParagraphStyle(
                "PayTotLbl",
                parent=styles["footer"],
                fontSize=7,
                textColor=_COLOR_MUTED,
                alignment=2,
            )
            pay_total_val = ParagraphStyle(
                "PayTotVal",
                parent=styles["meta_value"],
                fontSize=14,
                fontName="Helvetica-Bold",
                textColor=_COLOR_ACCENT,
                alignment=2,
                leading=17,
            )

            # Header row
            head_inner = Table(
                [[Paragraph(L["payment_info"].upper(), pay_head_style)]],
                colWidths=[page_width],
            )
            head_inner.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), _COLOR_HEADER_BG),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ]
                )
            )

            # Bank detail rows
            pay_rows = []
            if issuer_name:
                pay_rows.append(
                    [
                        Paragraph(L["bank_name"], pay_label_style),
                        Paragraph(html.escape(issuer_name), pay_val_style),
                    ]
                )
            if issuer_iban:
                pay_rows.append(
                    [
                        Paragraph(L["iban"], pay_label_style),
                        Paragraph(html.escape(issuer_iban), pay_val_style),
                    ]
                )
            if issuer_bic:
                pay_rows.append(
                    [
                        Paragraph(L["bic"], pay_label_style),
                        Paragraph(html.escape(issuer_bic), pay_val_style),
                    ]
                )

            detail_col_w = page_width - 4 * cm
            bank_tbl = Table(pay_rows, colWidths=[3 * cm, detail_col_w - 3 * cm])
            bank_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )

            right_block = [
                Paragraph(L["total"], pay_total_label),
                Paragraph(f"{invoice.total_amount:.2f}&nbsp;€", pay_total_val),
            ]

            body_inner = Table(
                [
                    [
                        Paragraph(
                            L["pay_request"].format(amount=f"{invoice.total_amount:.2f} €"),
                            pay_request_style,
                        ),
                        "",
                    ],
                    [bank_tbl, right_block],
                ],
                colWidths=[detail_col_w, 4 * cm],
            )
            body_inner.setStyle(
                TableStyle(
                    [
                        ("SPAN", (0, 0), (1, 0)),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (1, 1), (1, 1), "RIGHT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (-1, 0), (-1, -1), 12),
                        ("LEFTPADDING", (-1, 0), (-1, -1), 6),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.5, _COLOR_BORDER),
                    ]
                )
            )

            outer = Table(
                [[head_inner], [body_inner]],
                colWidths=[page_width],
            )
            outer.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 1.5, _COLOR_ACCENT),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            elements.append(outer)

        doc.build(elements)
        return buffer.getvalue()
    except Exception as exc:
        _pdf_logger.error("PDF generation failed for invoice %s: %s", invoice.pk, exc)
        raise
    finally:
        buffer.close()
