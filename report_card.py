"""
Generates a printable PDF report card for a student, using the same
term-and-subject aggregation (summed components) and CBE grading bands
as the web interface.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

SCHOOL_NAME = "St. Lucy's School for the Blind"
ACCENT_COLOR = colors.HexColor("#1d4d3f")
ACCENT_LIGHT = colors.HexColor("#e8f0ec")
BORDER_COLOR = colors.HexColor("#b8b2a4")


def cbe_full(score: float) -> str:
    if score >= 76:
        return "Exceeding Expectation (EE)"
    if score >= 51:
        return "Meeting Expectation (ME)"
    if score >= 26:
        return "Approaching Expectation (AE)"
    return "Below Expectation (BE)"


def aggregate_by_term_subject(results):
    """Groups raw result rows by term, then by subject, summing scores
    for entries that share the same term and subject."""
    term_map = {}
    term_order = []
    for r in results:
        if r.term not in term_map:
            term_map[r.term] = {}
            term_order.append(r.term)
        subj = term_map[r.term].setdefault(r.subject, {"total": 0.0, "components": []})
        subj["total"] += r.score
        subj["components"].append(r)
    return term_map, term_order


def build_report_card_pdf(student) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SchoolTitle", parent=styles["Title"], fontSize=17, textColor=ACCENT_COLOR, spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Heading2"], fontSize=13, textColor=colors.black, spaceAfter=10
    )
    info_style = ParagraphStyle("InfoLine", parent=styles["Normal"], fontSize=11, leading=16)
    term_heading_style = ParagraphStyle(
        "TermHeading", parent=styles["Heading3"], fontSize=12, textColor=ACCENT_COLOR, spaceBefore=10
    )
    summary_style = ParagraphStyle("Summary", parent=styles["Normal"], fontSize=11, leading=15)
    overall_style = ParagraphStyle(
        "Overall", parent=styles["Heading3"], fontSize=13, textColor=ACCENT_COLOR, spaceBefore=14
    )

    elements = []
    elements.append(Paragraph(SCHOOL_NAME, title_style))
    elements.append(Paragraph("Student Report Card", subtitle_style))

    class_name = student.school_class.name if student.school_class else "Unassigned"
    elements.append(Paragraph(f"<b>Name:</b> {student.name}", info_style))
    elements.append(Paragraph(f"<b>Registration number:</b> {student.reg_no}", info_style))
    elements.append(Paragraph(f"<b>Class:</b> {class_name}", info_style))
    elements.append(Spacer(1, 0.5 * cm))

    results = list(student.results)
    if not results:
        elements.append(Paragraph("No results have been recorded yet.", styles["Normal"]))
    else:
        term_map, term_order = aggregate_by_term_subject(results)
        all_subject_totals = []

        for term in term_order:
            elements.append(Paragraph(term, term_heading_style))
            data = [["Subject", "Score", "Level"]]
            subject_totals = []
            for subject, info in term_map[term].items():
                total = info["total"]
                subject_totals.append(total)
                all_subject_totals.append(total)
                data.append([subject, f"{total:.0f}%", cbe_full(total)])

            table = Table(data, colWidths=[7.5 * cm, 2.5 * cm, 6 * cm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT_LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            elements.append(table)

            term_avg = sum(subject_totals) / len(subject_totals) if subject_totals else 0
            elements.append(Spacer(1, 0.15 * cm))
            elements.append(Paragraph(
                f"<b>Term average: {term_avg:.1f}% — {cbe_full(term_avg)}</b>", summary_style
            ))

        overall_avg = sum(all_subject_totals) / len(all_subject_totals) if all_subject_totals else 0
        elements.append(Paragraph(
            f"Overall average: {overall_avg:.1f}% — {cbe_full(overall_avg)}", overall_style
        ))
        elements.append(Paragraph(
            f"Based on {len(results)} recorded entr{'y' if len(results) == 1 else 'ies'} "
            f"across {len(term_order)} term{'' if len(term_order) == 1 else 's'}.",
            styles["Normal"]
        ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
