"""
Service for generating EÜR (Einnahmenüberschussrechnung) PDFs.
"""

import logging as _logging
from decimal import Decimal
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

_logger = _logging.getLogger(__name__)

# Farbkonstanten — identisch zu billing/pdf_service.py (bewusste Kopie, kein Cross-App-Import)
_COLOR_DARK = colors.HexColor("#1e293b")
_COLOR_ACCENT = colors.HexColor("#2563eb")
_COLOR_LIGHT_BG = colors.HexColor("#f8fafc")
_COLOR_BORDER = colors.HexColor("#e2e8f0")
_COLOR_HEADER_BG = colors.HexColor("#1e293b")
_COLOR_HEADER_TEXT = colors.white
_COLOR_TOTAL_BG = colors.HexColor("#eff6ff")
_COLOR_WARNING = colors.HexColor("#92400e")
_COLOR_WARNING_BG = colors.HexColor("#fef3c7")
_COLOR_MUTED = colors.HexColor("#64748b")
_COLOR_LOSS = colors.HexColor("#c0392b")

_LABELS = {
    "de": {
        "title": "Einnahmenüberschussrechnung",
        "subtitle": "gemäß § 4 Abs. 3 EStG (Anlage EÜR)",
        "taxpayer": "Steuerpflichtiger",
        "tax_number": "Steuernummer",
        "fiscal_year": "Wirtschaftsjahr",
        "income_section": "Betriebseinnahmen",
        "income_invoices": "Bezahlte Ausgangsrechnungen (Zuflussprinzip)",
        "income_total": "Summe Betriebseinnahmen",
        "expenses_section": "Betriebsausgaben",
        "expenses_no_entries": "Keine Betriebsausgaben im Wirtschaftsjahr.",
        "expenses_total": "Summe Betriebsausgaben",
        "result_label": "Gewinn / Verlust (§ 4 Abs. 3 EStG)",
        "col_category": "Position",
        "col_amount": "Betrag (EUR)",
        "disclaimer": (
            "Hinweis: Diese Übersicht dient nur der Orientierung und ersetzt keine"
            " steuerliche Beratung. Bitte prüfen Sie alle Angaben sorgfältig und"
            " konsultieren Sie bei Bedarf einen Steuerberater oder Lohnsteuerhilfeverein."
        ),
    },
    "en": {
        "title": "Income Surplus Statement",
        "subtitle": "pursuant to § 4 para. 3 German Income Tax Act (EStG)",
        "taxpayer": "Taxpayer",
        "tax_number": "Tax number",
        "fiscal_year": "Fiscal year",
        "income_section": "Operating income",
        "income_invoices": "Paid outgoing invoices (cash basis)",
        "income_total": "Total operating income",
        "expenses_section": "Operating expenses",
        "expenses_no_entries": "No operating expenses recorded for this fiscal year.",
        "expenses_total": "Total operating expenses",
        "result_label": "Profit / Loss (§ 4 para. 3 EStG)",
        "col_category": "Category",
        "col_amount": "Amount (EUR)",
        "disclaimer": (
            "Note: This overview is for guidance only and does not replace professional"
            " tax advice. Please verify all figures carefully and consult a tax advisor"
            " if required."
        ),
    },
}


def _get_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "EuerTitle",
            parent=base["Normal"],
            fontSize=22,
            fontName="Helvetica-Bold",
            textColor=_COLOR_DARK,
            leading=26,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "EuerSubtitle",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=_COLOR_MUTED,
            leading=14,
        ),
        "year_badge": ParagraphStyle(
            "EuerYearBadge",
            parent=base["Normal"],
            fontSize=16,
            fontName="Helvetica-Bold",
            textColor=_COLOR_ACCENT,
            leading=20,
            alignment=2,  # RIGHT
        ),
        "section_heading": ParagraphStyle(
            "EuerSectionHeading",
            parent=base["Normal"],
            fontSize=8,
            fontName="Helvetica-Bold",
            textColor=_COLOR_MUTED,
            leading=12,
            spaceBefore=4,
            spaceAfter=3,
        ),
        "issuer_name": ParagraphStyle(
            "EuerIssuerName",
            parent=base["Normal"],
            fontSize=11,
            fontName="Helvetica-Bold",
            textColor=_COLOR_DARK,
            leading=15,
        ),
        "issuer_detail": ParagraphStyle(
            "EuerIssuerDetail",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=_COLOR_MUTED,
            leading=13,
        ),
        "table_cell": ParagraphStyle(
            "EuerCell",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=_COLOR_DARK,
            leading=13,
        ),
        "footer": ParagraphStyle(
            "EuerFooter",
            parent=base["Normal"],
            fontSize=8,
            fontName="Helvetica",
            textColor=_COLOR_MUTED,
            leading=12,
        ),
        "warning": ParagraphStyle(
            "EuerWarning",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=_COLOR_WARNING,
            leading=13,
            leftIndent=4,
            rightIndent=4,
        ),
    }


def _fmt_eur(amount: Decimal) -> str:
    """Format Decimal as German-style currency string, e.g. 1.234,56 €."""
    sign = "-" if amount < 0 else ""
    abs_val = abs(amount)
    formatted = f"{abs_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{formatted} €"


def _build_info_table(
    left_lines: list[tuple[str, str]],
    right_lines: list[tuple[str, str]],
    styles: dict,
    page_width: float,
) -> Table:
    max_rows = max(len(left_lines), len(right_lines), 1)
    while len(left_lines) < max_rows:
        left_lines.append(("", "issuer_detail"))
    while len(right_lines) < max_rows:
        right_lines.append(("", "issuer_detail"))

    rows = []
    for (lt, ls), (rt, rs) in zip(left_lines, right_lines, strict=True):
        rows.append([Paragraph(lt, styles[ls]), Paragraph(rt, styles[rs])])

    t = Table(rows, colWidths=[page_width * 0.6, page_width * 0.4])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BACKGROUND", (0, 0), (-1, -1), _COLOR_LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    return t


def _header_table_style() -> list:
    return [
        ("BACKGROUND", (0, 0), (-1, 0), _COLOR_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _COLOR_HEADER_TEXT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, _COLOR_BORDER),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("BACKGROUND", (0, 1), (-1, -2), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), _COLOR_TOTAL_BG),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, _COLOR_ACCENT),
    ]


def generate_euer_pdf(
    user,
    year: int,
    total_income: Decimal,
    expenses_by_category: dict,
    total_expenses: Decimal,
    profit: Decimal,
    language: str = "de",
) -> bytes:
    lang = language[:2].lower() if language else "de"
    if lang not in _LABELS:
        lang = "de"
    L = _LABELS[lang]

    # --- Profil-Daten (optional, fehlen = leere Strings) ---
    billing_name = ""
    billing_address = ""
    billing_tax_number = ""
    billing_email = ""
    try:
        profile = user.profile
        billing_name = getattr(profile, "billing_name", "") or ""
        billing_address = getattr(profile, "billing_address", "") or ""
        billing_tax_number = getattr(profile, "billing_tax_number", "") or ""
        billing_email = getattr(profile, "billing_email", "") or ""
    except Exception:  # noqa: BLE001
        _logger.debug("Could not load billing profile for user %s", user.pk)
    if not billing_name:
        billing_name = user.get_full_name() or user.username

    buffer = BytesIO()
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
    col_w = [page_width * 0.68, page_width * 0.32]
    elements = []

    # ── Kopfzeile: Titel links / Jahr rechts ────────────────────────────────
    header_row = Table(
        [
            [
                Paragraph(L["title"], styles["title"]),
                Paragraph(str(year), styles["year_badge"]),
            ]
        ],
        colWidths=[page_width * 0.75, page_width * 0.25],
    )
    header_row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(header_row)
    elements.append(Paragraph(L["subtitle"], styles["subtitle"]))
    elements.append(Spacer(1, 0.25 * cm))
    elements.append(HRFlowable(width=page_width, thickness=2, color=_COLOR_ACCENT, spaceAfter=6))

    # ── Steuerpflichtiger ────────────────────────────────────────────────────
    elements.append(Paragraph(L["taxpayer"].upper(), styles["section_heading"]))

    left_lines = [(billing_name, "issuer_name")]
    for raw_line in billing_address.splitlines():
        line = raw_line.strip()
        if line:
            left_lines.append((line, "issuer_detail"))

    right_lines = []
    if billing_tax_number:
        right_lines.append((f"{L['tax_number']}: {billing_tax_number}", "issuer_detail"))
    if billing_email:
        right_lines.append((billing_email, "issuer_detail"))
    right_lines.append((f"{L['fiscal_year']}: {year}", "issuer_detail"))

    elements.append(_build_info_table(left_lines, right_lines, styles, page_width))
    elements.append(Spacer(1, 0.5 * cm))

    # ── Betriebseinnahmen ────────────────────────────────────────────────────
    income_data = [
        [
            Paragraph(L["income_section"], styles["table_cell"]),
            Paragraph(L["col_amount"], styles["table_cell"]),
        ],
        [
            Paragraph(L["income_invoices"], styles["table_cell"]),
            Paragraph(_fmt_eur(total_income), styles["table_cell"]),
        ],
        [
            Paragraph(f"<b>{L['income_total']}</b>", styles["table_cell"]),
            Paragraph(f"<b>{_fmt_eur(total_income)}</b>", styles["table_cell"]),
        ],
    ]
    income_table = Table(income_data, colWidths=col_w)
    income_table.setStyle(TableStyle(_header_table_style()))
    elements.append(income_table)
    elements.append(Spacer(1, 0.4 * cm))

    # ── Betriebsausgaben ────────────────────────────────────────────────────
    expenses_data = [
        [
            Paragraph(L["expenses_section"], styles["table_cell"]),
            Paragraph(L["col_amount"], styles["table_cell"]),
        ],
    ]
    if expenses_by_category:
        for cat, amt in sorted(expenses_by_category.items()):
            expenses_data.append(
                [
                    Paragraph(cat, styles["table_cell"]),
                    Paragraph(_fmt_eur(amt), styles["table_cell"]),
                ]
            )
    else:
        expenses_data.append(
            [
                Paragraph(
                    f'<font color="#64748b"><i>{L["expenses_no_entries"]}</i></font>',
                    styles["table_cell"],
                ),
                Paragraph("", styles["table_cell"]),
            ]
        )
    expenses_data.append(
        [
            Paragraph(f"<b>{L['expenses_total']}</b>", styles["table_cell"]),
            Paragraph(f"<b>{_fmt_eur(total_expenses)}</b>", styles["table_cell"]),
        ]
    )

    style_cmds = _header_table_style()
    for i in range(1, len(expenses_data) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), _COLOR_LIGHT_BG))

    expenses_table = Table(expenses_data, colWidths=col_w)
    expenses_table.setStyle(TableStyle(style_cmds))
    elements.append(expenses_table)
    elements.append(Spacer(1, 0.4 * cm))

    # ── Ergebnis-Zeile (Gewinn / Verlust) ───────────────────────────────────
    is_loss = profit < Decimal("0")
    result_color = "#c0392b" if is_loss else "#1e293b"
    display_profit = abs(profit) if is_loss else profit
    profit_str = _fmt_eur(display_profit)
    if is_loss:
        profit_str = f"− {profit_str}"

    result_data = [
        [
            Paragraph(f"<b>{L['result_label']}</b>", styles["table_cell"]),
            Paragraph(
                f'<b><font color="{result_color}">{profit_str}</font></b>',
                styles["table_cell"],
            ),
        ]
    ]
    result_table = Table(result_data, colWidths=col_w)
    result_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _COLOR_TOTAL_BG),
                ("BOX", (0, 0), (-1, -1), 1.5, _COLOR_ACCENT),
                ("GRID", (0, 0), (-1, -1), 0.5, _COLOR_BORDER),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(result_table)
    elements.append(Spacer(1, 0.5 * cm))

    # ── Disclaimer-Box ───────────────────────────────────────────────────────
    disclaimer_table = Table(
        [[Paragraph(f"⚠ {L['disclaimer']}", styles["warning"])]],
        colWidths=[page_width],
    )
    disclaimer_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _COLOR_WARNING_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(disclaimer_table)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
