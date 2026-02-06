from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, Color
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Spacer,
    Paragraph,
    Image,
    PageBreak,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER


def _ordinal(n):
    """Return ordinal string for an integer (1st, 2nd, 3rd, 4th, ...)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_date(date_str):
    """Convert YYYY-MM-DD to 'Sunday, February 6th, 2026' format.

    Returns the original string if parsing fails.
    """
    if not date_str:
        return date_str
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = dt.strftime("%A")
        month_name = dt.strftime("%B")
        day_ordinal = _ordinal(dt.day)
        year = dt.year
        return f"{day_name}, {month_name} {day_ordinal}, {year}"
    except (ValueError, TypeError):
        return date_str


def generate_pdf(
    boards,
    title="Sermon BINGO",
    church_name="",
    logo_path=None,
    header_color="#2c3e50",
    border_color="#34495e",
    board_size=5,
    card_date="",
    card_occasion="",
    footer_message="",
):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.4 * inch,
        bottomMargin=0.4 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    title_style = ParagraphStyle(
        "title",
        alignment=TA_CENTER,
        fontSize=28,
        fontName="Helvetica-Bold",
        spaceAfter=6,
        textColor=HexColor(header_color),
    )

    church_style = ParagraphStyle(
        "church",
        alignment=TA_CENTER,
        fontSize=14,
        fontName="Helvetica",
        spaceAfter=4,
        textColor=HexColor(header_color),
    )

    card_num_style = ParagraphStyle(
        "cardnum",
        alignment=TA_CENTER,
        fontSize=10,
        fontName="Helvetica",
        spaceBefore=8,
        textColor=colors.grey,
    )

    date_style = ParagraphStyle(
        "date",
        alignment=TA_CENTER,
        fontSize=11,
        fontName="Helvetica",
        spaceBefore=2,
        textColor=colors.grey,
    )

    footer_msg_style = ParagraphStyle(
        "footer_msg",
        alignment=TA_CENTER,
        fontSize=10,
        fontName="Helvetica-Oblique",
        spaceBefore=4,
        textColor=colors.grey,
    )

    cell_style = ParagraphStyle(
        "cell",
        alignment=TA_CENTER,
        fontSize=14,
        fontName="Helvetica",
        leading=16,
    )

    cell_style_small = ParagraphStyle(
        "cell_small",
        alignment=TA_CENTER,
        fontSize=11,
        fontName="Helvetica",
        leading=13,
    )

    free_style = ParagraphStyle(
        "free",
        alignment=TA_CENTER,
        fontSize=18,
        fontName="Helvetica-Bold",
        textColor=white,
    )

    story = []
    total_cards = len(boards)

    for card_idx, board in enumerate(boards):
        # Logo
        if logo_path:
            try:
                img = Image(logo_path)
                # Scale to max 0.8 inch, maintain aspect ratio
                aspect = img.imageWidth / img.imageHeight if img.imageHeight else 1
                if aspect >= 1:
                    img.drawWidth = 0.8 * inch
                    img.drawHeight = 0.8 * inch / aspect
                else:
                    img.drawHeight = 0.8 * inch
                    img.drawWidth = 0.8 * inch * aspect
                img.hAlign = "CENTER"
                story.append(img)
                story.append(Spacer(1, 4))
            except Exception:
                pass  # Skip logo if there's an issue

        # Church name
        if church_name:
            story.append(Paragraph(church_name, church_style))

        # Title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))

        # Build table data
        page_width = letter[0] - 1.5 * inch  # usable width after margins
        cell_size = page_width / board_size   # fill the full width so grid is square

        table_data = []

        # BINGO headers for 5x5
        if board_size == 5:
            headers = ["B", "I", "N", "G", "O"]
            table_data.append(headers)

        # Board rows - wrap words in Paragraphs for text wrapping
        for row in board:
            row_data = []
            for cell_val in row:
                if cell_val == "FREE":
                    row_data.append(Paragraph("FREE", free_style))
                else:
                    word = cell_val.capitalize()
                    style = cell_style_small if len(word) > 12 else cell_style
                    row_data.append(Paragraph(word, style))
            table_data.append(row_data)

        col_widths = [cell_size] * board_size
        # All rows same height as width so every cell is a perfect square
        row_heights = [cell_size] * len(table_data)

        table = Table(table_data, colWidths=col_widths, rowHeights=row_heights)

        # Table styling
        style_commands = [
            # Grid
            ("GRID", (0, 0), (-1, -1), 2, HexColor(border_color)),
            # Center everything
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            # Reduce padding so text can be larger and closer to edges
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]

        if board_size == 5:
            # Header row styling
            style_commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor(header_color)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 20),
                    # FREE space (row 3 = header + 2 data rows, col 2)
                    ("BACKGROUND", (2, 3), (2, 3), HexColor("#f39c12")),
                ]
            )

        # Alternate row backgrounds for readability (light gray on even data rows)
        start_row = 1 if board_size == 5 else 0
        for i in range(board_size):
            actual_row = start_row + i
            if i % 2 == 1:
                style_commands.append(
                    ("BACKGROUND", (0, actual_row), (-1, actual_row), HexColor("#f8f9fa"))
                )

        table.setStyle(TableStyle(style_commands))
        table.hAlign = "CENTER"
        story.append(table)

        # Footer: card number, optional date, and optional occasion
        footer_parts = []
        if card_date:
            footer_parts.append(format_date(card_date))
        if card_occasion:
            footer_parts.append(card_occasion)
        footer_parts.append(f"Card {card_idx + 1} of {total_cards}")
        story.append(
            Paragraph(" &nbsp;&bull;&nbsp; ".join(footer_parts), card_num_style)
        )

        # Optional footer message
        if footer_message:
            story.append(Paragraph(footer_message, footer_msg_style))

        # Page break (except after last card)
        if card_idx < total_cards - 1:
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer
