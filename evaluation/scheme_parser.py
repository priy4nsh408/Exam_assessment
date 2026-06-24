"""
Answer Scheme Parser
====================
OCR an uploaded answer scheme PDF/image and extract structured question data:
  subject, [{q_number, question, reference_answer, max_marks}, ...]

Parsing strategy:
  1. OCR the file (reuse ocr_engine)
  2. Detect subject from header lines
  3. Segment text by question boundaries — many formats supported
  4. Within each segment, split into question text vs. answer text
  5. Extract marks from patterns like "(5M)", "[10]", "5 marks", "Marks: 5"
"""

from __future__ import annotations
import re
from typing import List, Dict, Tuple

from evaluation.ocr_engine import ocr_pdf, ocr_image_file


# ── Subject detection ─────────────────────────────────────────────────────────

_SUBJECT_RE = re.compile(
    r"(?:subject|course|paper|title|exam)\s*[:\-]\s*(.+)", re.I
)

# Also try to grab subject from the filename or document title lines
_TITLE_KEYWORDS = re.compile(
    r"\b(thermodynamics|fluid\s*mechanics|strength\s*of\s*materials|"
    r"machine\s*design|engineering\s*drawing|manufacturing|"
    r"aerospace|structures?|propulsion|mechanics|dynamics|"
    r"structural|mechanical)\b", re.I
)


# ── Marks extraction ──────────────────────────────────────────────────────────

_MARKS_RE = re.compile(
    r"\[(\d+)\s*(?:M|marks?)?\]"           # [5M]  [10]  [5 marks]
    r"|\((\d+)\s*(?:M|marks?)?\)"          # (5M)  (10)  (5 marks)
    r"|(\d+)\s*marks?"                     # 5 marks
    r"|marks?\s*[:\-]\s*(\d+)"            # marks: 5
    r"|(?:^|\s)(\d+)\s*M(?:\s|$|\]|\))"  # 5M  10M
    r"|\bM\b\s*[:\-]\s*(\d+)",            # M: 5
    re.I | re.MULTILINE,
)


# ── Question boundary patterns (many real-world formats) ─────────────────────

# Each pattern: (regex, group_index_for_number)
_Q_PATTERNS: List[Tuple[re.Pattern, int]] = [
    # "Question 1"  "Q1"  "Q.1"  "Q 1"
    (re.compile(r"(?mi)^[\s]*(?:question|q)\.?\s*(\d+)[\s\.\:\)\-]"), 1),
    # "1."  "1)"  "1:"  at start of line  (with optional space after)
    (re.compile(r"(?m)^[\s]*(\d{1,2})[\.:\)]\s"), 1),
    # "1 ." or "l." (OCR sometimes reads 1 as l)
    (re.compile(r"(?m)^[\s]*(\d{1,2})\s[\.:\)]"), 1),
    # "Answer 1"  "Ans 1"  "Ans. 1"
    (re.compile(r"(?mi)^[\s]*ans(?:wer)?\.?\s*(\d+)[\s\.\:\)\-]"), 1),
    # "(1)"  "(2)"  at start of line
    (re.compile(r"(?m)^[\s]*\((\d{1,2})\)"), 1),
    # "Part 1"  "Part A"→skip letters, numbers only
    (re.compile(r"(?mi)^[\s]*part[\s\-\.]*(\d+)"), 1),
    # "Problem 1"
    (re.compile(r"(?mi)^[\s]*problem\s*(\d+)[\s\.\:\)\-]"), 1),
    # "No. 1"  "No 1"
    (re.compile(r"(?mi)^[\s]*no\.?\s*(\d+)[\s\.\:\)\-]"), 1),
]


def _find_boundaries(text: str):
    """
    Find all question boundary positions in text.
    Returns sorted list of (char_position, q_number, match).
    Tries all patterns and deduplicates overlapping matches.
    """
    hits = []
    for pat, grp in _Q_PATTERNS:
        for m in pat.finditer(text):
            try:
                q_num = int(m.group(grp))
                if 1 <= q_num <= 50:          # sanity check: valid question numbers
                    hits.append((m.start(), q_num, m))
            except (ValueError, IndexError):
                pass

    if not hits:
        return []

    # Sort by position, deduplicate overlapping matches (keep first hit per position window)
    hits.sort(key=lambda x: x[0])
    deduped = [hits[0]]
    for pos, qnum, m in hits[1:]:
        last_pos = deduped[-1][0]
        if pos - last_pos > 5:               # more than 5 chars apart = different match
            deduped.append((pos, qnum, m))

    # Validate: question numbers should be roughly sequential (1,2,3 or 1,2,4 etc)
    # Filter out spurious matches where number jumps by >5 unexpectedly
    validated = [deduped[0]]
    for pos, qnum, m in deduped[1:]:
        last_qnum = validated[-1][1]
        if qnum > last_qnum and qnum <= last_qnum + 5:
            validated.append((pos, qnum, m))
        elif qnum == last_qnum + 0:          # same number = sub-part, skip
            pass

    return validated


# ── Answer split ──────────────────────────────────────────────────────────────

_ANS_START = re.compile(
    r"(?:ans(?:wer)?|sol(?:ution)?|explanation|model\s*answer)\s*[:\-]?\s*", re.I
)


def _split_question_answer(segment_text: str) -> Tuple[str, str]:
    """Split segment into (question_text, answer_text)."""
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
    if 0 < qmark < len(segment_text) * 0.6:
        return segment_text[:qmark + 1].strip(), segment_text[qmark + 1:].strip()

    # Fallback: first 1-2 lines = question, rest = answer
    lines = [l for l in segment_text.strip().splitlines() if l.strip()]
    if len(lines) >= 3:
        split = max(1, min(2, len(lines) // 3))
        return "\n".join(lines[:split]).strip(), "\n".join(lines[split:]).strip()
    if len(lines) == 2:
        return lines[0].strip(), lines[1].strip()
    return segment_text.strip(), ""


# ── Subject detection ─────────────────────────────────────────────────────────

def _detect_subject(full_text: str, filename: str = "") -> str:
    """Look for subject in header lines or filename."""
    # Check first 15 lines for explicit subject label
    for line in full_text.splitlines()[:15]:
        m = _SUBJECT_RE.search(line)
        if m:
            return m.group(1).strip()[:80]

    # Try to find subject keywords in first 20 lines
    header = "\n".join(full_text.splitlines()[:20])
    m = _TITLE_KEYWORDS.search(header)
    if m:
        # Return the surrounding context (up to 60 chars)
        start = max(0, m.start() - 10)
        end   = min(len(header), m.end() + 20)
        return header[start:end].strip()[:80]

    # Try filename
    if filename:
        clean = re.sub(r"[_\-\.\(\)0-9]+", " ", filename).strip()
        clean = re.sub(r"\s+", " ", clean)
        m = _TITLE_KEYWORDS.search(clean)
        if m:
            return clean[:80]

    return ""


# ── Marks extraction helper ───────────────────────────────────────────────────

def _extract_marks(text: str, default: int = 10) -> int:
    m = _MARKS_RE.search(text)
    if m:
        val = next((g for g in m.groups() if g is not None), None)
        if val:
            return min(int(val), 100)   # cap at 100
    return default


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
        "subject":        str,
        "questions":      [{q_number, question, reference_answer, max_marks, type}, ...],
        "raw_text":       str,   # full OCR text for debugging
        "parse_warnings": [str],
      }
    """
    import os
    filename = os.path.basename(file_path)

    # OCR
    if file_path.lower().endswith(".pdf"):
        pages = ocr_pdf(file_path)
    else:
        pages = ocr_image_file(file_path)

    full_text = "\n\n".join(p["text"] for p in pages)
    warnings: List[str] = []

    if not full_text.strip():
        warnings.append(
            "OCR returned no text. "
            "Check that easyocr and pdf2image are installed and the file is a clear scan."
        )
        return {
            "subject": subject_hint or "Unknown",
            "questions": [],
            "raw_text": "",
            "parse_warnings": warnings,
        }

    # Subject
    subject = subject_hint.strip() or _detect_subject(full_text, filename) or "Unknown"

    # Find question boundaries
    boundaries = _find_boundaries(full_text)

    if not boundaries:
        # Last resort: try to split on double-newlines and number them
        warnings.append(
            "Could not detect question boundaries automatically. "
            "The scheme will be treated as a single reference answer. "
            "For best results, number your questions as '1.' or 'Q1.' or 'Question 1'."
        )
        # Return the whole text as Q1 reference answer
        return {
            "subject": subject,
            "questions": [{
                "q_number":         1,
                "question":         "",
                "reference_answer": full_text.strip()[:3000],
                "max_marks":        default_marks,
                "type":             None,
            }],
            "raw_text": full_text,
            "parse_warnings": warnings,
        }

    questions: List[Dict] = []
    for idx, (pos, qnum, m) in enumerate(boundaries):
        start = m.end()
        end   = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(full_text)
        segment = full_text[start:end].strip()

        if not segment:
            continue

        marks = _extract_marks(segment, default=default_marks)
        clean = _MARKS_RE.sub("", segment).strip()
        q_text, a_text = _split_question_answer(clean)

        questions.append({
            "q_number":         qnum,
            "question":         q_text[:500],
            "reference_answer": a_text[:2000],
            "max_marks":        marks,
            "type":             None,
        })

    if not questions:
        warnings.append("Question boundaries found but all segments were empty.")

    return {
        "subject":        subject,
        "questions":      questions,
        "raw_text":       full_text[:5000],   # first 5000 chars for debug
        "parse_warnings": warnings,
    }
