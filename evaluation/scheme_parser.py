"""
Answer Scheme Parser
====================
OCR an uploaded answer scheme PDF/image and extract structured question data:
  subject, [{q_number, question, reference_answer, max_marks}, ...]

Parsing strategy:
  1. OCR the file (reuse ocr_engine)
  2. Detect subject from header lines ("Subject: ...", "Course: ...")
  3. Segment text by question boundaries (Q1, 1., Question 1, etc.)
  4. Within each segment, split into question text vs. answer text
     (answer usually follows "Ans:", "Answer:", "Sol:", a blank line, or just continues)
  5. Extract marks from patterns like "(5M)", "[10]", "5 marks", "Marks: 5"

Returns a dict the evaluator pipeline can consume directly as exam_questions.
"""

from __future__ import annotations
import re
from typing import List, Dict, Optional

from evaluation.ocr_engine import ocr_pdf, ocr_image_file


# ── Regex patterns ────────────────────────────────────────────────────────────

_SUBJECT_RE = re.compile(
    r"(?:subject|course|paper|title)\s*[:\-]\s*(.+)", re.I
)

_MARKS_RE = re.compile(
    r"\[(\d+)\s*(?:M|marks?)?\]"          # [5M]  [10]  [5 marks]
    r"|\((\d+)\s*(?:M|marks?)?\)"         # (5M)  (10)  (5 marks)
    r"|(\d+)\s*marks?"                    # 5 marks  5 mark
    r"|marks?\s*[:\-]\s*(\d+)"           # marks: 5  marks - 10
    r"|(?:\bM\b\s*[:\-]\s*(\d+))",       # M: 5
    re.I,
)

_Q_BOUNDARY = re.compile(
    r"(?m)^[\s]*(?:"
    r"(?:question|q)\.?\s*(\d+)"         # Question 1  Q1  Q.1
    r"|(\d+)[.)]\s"                       # 1.  1)
    r"|(?:ans(?:wer)?\.?\s*(\d+))"       # Answer 1  Ans 1
    r")",
)

_ANS_START = re.compile(
    r"(?:ans(?:wer)?|sol(?:ution)?|explanation)\s*[:\-]?\s*", re.I
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_marks(text: str, default: int = 10) -> int:
    m = _MARKS_RE.search(text)
    if m:
        val = next(g for g in m.groups() if g is not None)
        return int(val)
    return default


def _split_question_answer(segment_text: str):
    """
    Split a segment into (question_text, answer_text).
    Heuristic: answer starts after explicit "Ans:"/"Sol:" marker,
    or after first blank line, or after the first sentence ending in '?'.
    """
    # Explicit marker
    m = _ANS_START.search(segment_text)
    if m:
        q = segment_text[:m.start()].strip()
        a = segment_text[m.end():].strip()
        return q, a

    # Blank line split
    parts = re.split(r"\n\s*\n", segment_text, maxsplit=1)
    if len(parts) == 2 and parts[0].strip():
        return parts[0].strip(), parts[1].strip()

    # Question mark heuristic
    qmark = segment_text.find("?")
    if qmark != -1 and qmark < len(segment_text) // 2:
        return segment_text[:qmark + 1].strip(), segment_text[qmark + 1:].strip()

    # Fallback: first line is question, rest is answer
    lines = segment_text.strip().splitlines()
    if len(lines) > 1:
        return lines[0].strip(), "\n".join(lines[1:]).strip()
    return segment_text.strip(), ""


def _detect_subject(full_text: str) -> str:
    """Look for subject/course header in first 10 lines."""
    for line in full_text.splitlines()[:10]:
        m = _SUBJECT_RE.search(line)
        if m:
            return m.group(1).strip()
    return ""


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_answer_scheme(
    file_path: str,
    subject_hint: str = "",
    default_marks: int = 10,
) -> Dict:
    """
    Parse an answer scheme PDF or image.

    Returns:
      {
        "subject":   str,
        "questions": [
          {
            "q_number":         int,
            "question":         str,
            "reference_answer": str,
            "max_marks":        int,
            "type":             str | None,   # filled by classify later if needed
          }, ...
        ],
        "parse_warnings": [str],
      }
    """
    # OCR
    if file_path.lower().endswith(".pdf"):
        pages = ocr_pdf(file_path)
    else:
        pages = ocr_image_file(file_path)

    full_text = "\n\n".join(p["text"] for p in pages)
    warnings: List[str] = []

    if not full_text.strip():
        warnings.append("OCR returned no text — check scan quality or install easyocr/pdf2image.")
        return {"subject": subject_hint or "Unknown", "questions": [], "parse_warnings": warnings}

    # Subject detection
    subject = subject_hint or _detect_subject(full_text) or "Unknown"

    # Segment by question boundaries
    matches = list(_Q_BOUNDARY.finditer(full_text))

    def _q_num(m: re.Match) -> int:
        return int(next(g for g in m.groups() if g is not None))

    if not matches:
        warnings.append(
            "No question boundaries detected. "
            "Make sure the scheme has markers like 'Q1.', '1.', 'Question 1', etc."
        )
        return {"subject": subject, "questions": [], "parse_warnings": warnings}

    questions: List[Dict] = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        segment = full_text[start:end].strip()

        marks = _extract_marks(segment, default=default_marks)
        # Remove marks pattern from segment before splitting q/a
        clean = _MARKS_RE.sub("", segment).strip()
        q_text, a_text = _split_question_answer(clean)

        questions.append({
            "q_number":         _q_num(m),
            "question":         q_text[:500],       # cap to avoid bloat
            "reference_answer": a_text[:2000],
            "max_marks":        marks,
            "type":             None,               # auto-classified during eval
        })

    if not questions:
        warnings.append("Question boundaries found but segments were empty.")

    return {
        "subject":        subject,
        "questions":      questions,
        "parse_warnings": warnings,
    }
