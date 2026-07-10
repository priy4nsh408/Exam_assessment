"""
Renders exams as college-format PDFs (question paper / answer scheme),
matching the RVCE department letterhead: running header with crest,
academic year, USN line, department name; a title block with course
code/date/semester/duration; a single SL.No/Questions/Marks/BT/CO table
that repeats its header across page breaks; and footer Course Outcome +
Marks Distribution tables computed from the exam's actual questions.
"""

import re
from pathlib import Path
from typing import List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

LOGO_PATH = Path(__file__).parent / "assets" / "college_logo.png"
DEFAULT_COLLEGE_NAME_LINES = ["RV College of", "Engineering"]
DEFAULT_COLLEGE_MOTTO = "Go, change the world"
DEFAULT_DEPARTMENT = "Department of Artificial Intelligence and Machine Learning"
CO_CODES = ["CO1", "CO2", "CO3", "CO4", "CO5"]
BT_LEVELS = [1, 2, 3, 4, 5, 6]


def _co_number(co: str) -> str:
    digits = re.sub(r"[^0-9]", "", co or "")
    return digits or (co or "")


def _html(text: Optional[str]) -> str:
    return escape(text or "").replace("\n", "<br/>")


def _draw_header(canvas, doc, exam: dict):
    canvas.saveState()
    width, height = doc.pagesize
    left = doc.leftMargin
    right = width - doc.rightMargin
    top = height - 24

    text_x = left
    if LOGO_PATH.exists():
        logo_size = 46
        try:
            canvas.drawImage(
                str(LOGO_PATH), left, top - logo_size + 4,
                width=logo_size, height=logo_size,
                preserveAspectRatio=True, mask="auto",
            )
            text_x = left + logo_size + 10
        except Exception:
            pass

    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(text_x, top - 10, DEFAULT_COLLEGE_NAME_LINES[0])
    canvas.drawString(text_x, top - 23, DEFAULT_COLLEGE_NAME_LINES[1])

    canvas.setFont("Helvetica-Oblique", 10)
    canvas.drawRightString(right, top - 8, DEFAULT_COLLEGE_MOTTO)

    canvas.setFont("Helvetica-Bold", 8.5)
    academic_year = exam.get("academic_year") or ""
    year_line = f"Academic Year {academic_year}".strip() if academic_year else "Academic Year"
    canvas.drawRightString(right, top - 22, year_line)
    canvas.drawRightString(right, top - 34, "USN:")

    canvas.setFont("Helvetica-Bold", 12.5)
    dept = exam.get("department") or DEFAULT_DEPARTMENT
    canvas.drawCentredString(width / 2, top - 50, dept)
    canvas.setLineWidth(1)
    canvas.line(left, top - 56, right, top - 56)
    canvas.restoreState()


def _make_doc(buffer, exam: dict) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=32, rightMargin=32, topMargin=95, bottomMargin=36,
        title=exam.get("title") or "Exam Paper",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    template = PageTemplate(id="exam", frames=[frame], onPage=lambda c, d: _draw_header(c, d, exam))
    doc.addPageTemplates([template])
    return doc


def _styles():
    base = getSampleStyleSheet()
    body = ParagraphStyle("examBody", parent=base["Normal"], fontSize=9.5, leading=13, alignment=TA_JUSTIFY)
    center = ParagraphStyle("examCenter", parent=base["Normal"], fontSize=9.5, alignment=TA_CENTER)
    bold_center = ParagraphStyle("examBoldCenter", parent=center, fontName="Helvetica-Bold")
    info = ParagraphStyle("examInfo", parent=base["Normal"], fontSize=9.5)
    title = ParagraphStyle("examTitle", parent=base["Normal"], fontSize=11, fontName="Helvetica-Bold",
                            alignment=TA_CENTER, spaceAfter=2)
    subtitle = ParagraphStyle("examSubtitle", parent=title, fontSize=10)
    answer_all = ParagraphStyle("examAnswerAll", parent=subtitle, fontSize=9.5, fontName="Helvetica-BoldOblique")
    note = ParagraphStyle("examNote", parent=base["Normal"], fontSize=8, fontName="Helvetica-Oblique")
    return {
        "body": body, "center": center, "bold_center": bold_center, "info": info,
        "title": title, "subtitle": subtitle, "answer_all": answer_all, "note": note,
    }


def _title_block(doc, exam: dict, styles: dict) -> list:
    s = styles
    info_data = [
        [Paragraph(f"<b>Course Code:</b> {_html(exam.get('course_code'))}", s["info"]),
         Paragraph(f"<b>Date:</b> {_html(exam.get('exam_date'))}", s["info"])],
        [Paragraph(f"<b>Sem:</b> {_html(exam.get('semester'))}", s["info"]),
         Paragraph(f"<b>Duration:</b> {exam.get('duration', '')} Minutes", s["info"])],
    ]
    info_table = Table(info_data, colWidths=[doc.width / 2, doc.width / 2])
    info_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [
        info_table,
        Spacer(1, 6),
        Paragraph(_html(exam.get("cie_label") or "Question Paper"), s["title"]),
        Paragraph(_html(exam.get("subject")), s["subtitle"]),
        Paragraph("Answer all Questions", s["answer_all"]),
        Spacer(1, 6),
    ]


def _question_table(doc, questions: List[dict], mode: str, styles: dict) -> Table:
    s = styles
    header_row = [
        Paragraph("<b>SL. No</b>", s["bold_center"]),
        Paragraph("<b>Questions</b>", s["bold_center"]),
        Paragraph("<b>Marks</b>", s["bold_center"]),
        Paragraph("<b>BT</b>", s["bold_center"]),
        Paragraph("<b>CO</b>", s["bold_center"]),
    ]
    rows = [header_row]
    for i, q in enumerate(questions, start=1):
        cell = [Paragraph(_html(q.get("text")), s["body"])]
        if mode == "scheme":
            answer = q.get("answerKey")
            if answer:
                cell += [Spacer(1, 4), Paragraph("<b>Model Answer:</b>", s["body"]),
                         Paragraph(_html(answer), s["body"])]
            explanation = q.get("answerKeyExplanation")
            if explanation:
                cell += [Spacer(1, 4), Paragraph("<b>Validation:</b>", s["body"]),
                         Paragraph(_html(explanation), s["body"])]
        rows.append([
            Paragraph(str(i), s["center"]),
            cell,
            Paragraph(str(q.get("marks", "")), s["center"]),
            Paragraph(str(q.get("bloomLevel", "")), s["center"]),
            Paragraph(_co_number(q.get("co")), s["center"]),
        ])

    col_widths = [0.06 * doc.width, 0.68 * doc.width, 0.09 * doc.width, 0.08 * doc.width, 0.09 * doc.width]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _co_description_table(doc, co_descriptions: dict, styles: dict) -> Optional[Table]:
    s = styles
    left_bold = ParagraphStyle("coLeft", parent=s["body"], fontName="Helvetica-Bold", alignment=TA_CENTER)
    data = [[Paragraph("<b>Course Outcome</b>", left_bold), ""]]
    for co in CO_CODES:
        desc = co_descriptions.get(co)
        if not desc:
            continue
        data.append([Paragraph(f"<b>{co}</b>", left_bold), Paragraph(_html(desc), s["body"])])
    if len(data) == 1:
        return None
    table = Table(data, colWidths=[0.08 * doc.width, 0.92 * doc.width])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _marks_distribution_table(doc, questions: List[dict], styles: dict) -> Table:
    s = styles
    marks_by_co, marks_by_bt = {}, {}
    for q in questions:
        marks = q.get("marks") or 0
        co_num = _co_number(q.get("co"))
        if co_num:
            marks_by_co[co_num] = marks_by_co.get(co_num, 0) + marks
        bt = q.get("bloomLevel")
        if bt:
            marks_by_bt[bt] = marks_by_bt.get(bt, 0) + marks

    def co_val(co_code: str) -> str:
        v = marks_by_co.get(_co_number(co_code))
        return str(v) if v else "--"

    def bt_val(level: int) -> str:
        v = marks_by_bt.get(level)
        return str(v) if v else "--"

    header_row = (
        [Paragraph("<b>Marks<br/>Distribution</b>", s["bold_center"]), Paragraph("<b>Particulars</b>", s["bold_center"])]
        + [Paragraph(f"<b>{c}</b>", s["bold_center"]) for c in CO_CODES]
        + [Paragraph(f"<b>L{n}</b>", s["bold_center"]) for n in BT_LEVELS]
    )
    data_row = (
        [Paragraph("", s["center"]), Paragraph("<b>Max Marks</b>", s["bold_center"])]
        + [Paragraph(co_val(c), s["center"]) for c in CO_CODES]
        + [Paragraph(bt_val(n), s["center"]) for n in BT_LEVELS]
    )

    col_widths = [0.13 * doc.width, 0.13 * doc.width] + [(0.74 * doc.width) / 11] * 11
    table = Table([header_row, data_row], colWidths=col_widths)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("SPAN", (0, 0), (0, 1)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def generate_exam_pdf(
    exam: dict,
    questions: List[dict],
    mode: str = "paper",
    co_descriptions: Optional[dict] = None,
) -> bytes:
    """
    Build a college-format exam PDF and return it as raw PDF bytes.

    `exam` uses the DB's snake_case keys: title, subject, duration,
    course_code, semester, cie_label, exam_date, academic_year, department.
    `questions` uses the API's camelCase keys (text, marks, bloomLevel, co,
    and for mode="scheme" also answerKey/answerKeyExplanation).
    mode="paper" renders a blank question paper; mode="scheme" additionally
    prints the model answer + validation note under each question.
    """
    from io import BytesIO

    co_descriptions = co_descriptions or {}
    buffer = BytesIO()
    doc = _make_doc(buffer, exam)
    styles = _styles()

    story = []
    story += _title_block(doc, exam, styles)
    story.append(_question_table(doc, questions, mode, styles))

    co_table = _co_description_table(doc, co_descriptions, styles)
    if co_table:
        story.append(Spacer(1, 8))
        story.append(co_table)

    story.append(Spacer(1, 6))
    story.append(Paragraph("M-Marks, BT-Blooms Taxonomy Levels, CO-Course Outcomes", styles["note"]))
    story.append(Spacer(1, 2))
    story.append(_marks_distribution_table(doc, questions, styles))

    doc.build(story)
    return buffer.getvalue()
