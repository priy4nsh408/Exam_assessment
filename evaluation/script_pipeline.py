"""
Answer-Script Pipeline
======================
PDF/image upload → OCR → answer segmentation → type classification
→ theory / numerical / drawing evaluator → aggregate report

Public entry points:
  evaluate_answer_script(file_path, ...)
  evaluate_multiple_scripts(file_paths, ...)   ← batch
"""

from __future__ import annotations
import re
from typing import List, Dict, Optional, Any

from evaluation.ocr_engine import (
    ocr_pdf, ocr_image_file, get_dependency_status
)


# ── lazy evaluator imports ───────────────────────────────────────────────────
def _theory():
    from evaluation.theory_evaluator import evaluate_theory
    return evaluate_theory

def _numerical():
    from evaluation.numerical_grader import grade_numerical
    return grade_numerical

def _drawing():
    from evaluation.drawing_evaluator import evaluate_drawing
    return evaluate_drawing


# ── Question-type classifier ─────────────────────────────────────────────────
_NUMERICAL_SIGNALS = re.compile(
    r"\b(calculat|comput|find|determin|evaluat|solv|value of|"
    r"how much|how many|express in|in units|mpa|kpa|kn|rpm|"
    r"stress|strain|force|moment|torque|velocity|pressure|"
    r"temperature|efficiency|power|energy|heat|work|"
    r"area|volume|length|diameter|radius|shear|bending|"
    r"modulus|poisson|thermal|conductivity|viscosity)\b", re.I,
)
_DRAWING_SIGNALS = re.compile(
    r"\b(draw|sketch|illustrat|show (the|a)|diagram|label|mark|"
    r"cross.?section|isometric|orthograph|projection|free.?body|fbd|"
    r"shear force|bending moment|t.?s diagram|p.?v diagram)\b", re.I,
)
_THEORY_SIGNALS = re.compile(
    r"\b(explain|describe|define|state|list|discuss|differentiat|compare|"
    r"what (is|are|do)|how does|why|advantages|disadvantages|"
    r"principle|concept|law|theorem|classification|types of)\b", re.I,
)


def classify_question_type(text: str) -> str:
    scores = {
        "drawing":   len(_DRAWING_SIGNALS.findall(text)),
        "numerical": len(_NUMERICAL_SIGNALS.findall(text)),
        "theory":    len(_THEORY_SIGNALS.findall(text)),
    }
    return max(scores, key=scores.get)  # type: ignore[arg-type]


# ── Answer segmentation ──────────────────────────────────────────────────────
_ANSWER_BOUNDARY = re.compile(
    r"(?m)^[\s]*(?:"
    r"(?:ans(?:wer)?\.?\s*)?[Qq](?:uestion)?\.?\s*(\d+)"
    r"|(\d+)[.)]\s"
    r"|(?:ans(?:wer)?\.?\s*(\d+))"
    r")",
)


def segment_answers(pages: List[Dict]) -> List[Dict]:
    """Detect Q-boundaries across all pages; fall back to one segment per page."""
    full_text = ""
    page_offsets: List[tuple] = []
    for p in pages:
        page_offsets.append((len(full_text), p["image_path"], p.get("confidence", 1.0)))
        full_text += p["text"] + "\n\n"

    matches = list(_ANSWER_BOUNDARY.finditer(full_text))

    def _q_num(m: re.Match) -> int:
        return int(next(g for g in m.groups() if g is not None))

    def _img_conf_for_offset(offset: int):
        img, conf = page_offsets[0][1], page_offsets[0][2]
        for char_off, path, c in page_offsets:
            if char_off <= offset:
                img, conf = path, c
        return img, conf

    if not matches:
        return [
            {
                "q_number": i,
                "text": p["text"],
                "image_paths": [p["image_path"]],
                "page_start": p["page"],
                "ocr_confidence": p.get("confidence", 1.0),
                "low_confidence": p.get("low_confidence", False),
            }
            for i, p in enumerate(pages, start=1)
        ]

    segments: List[Dict] = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        img, conf = _img_conf_for_offset(m.start())
        segments.append({
            "q_number": _q_num(m),
            "text": full_text[start:end].strip(),
            "image_paths": [img],
            "page_start": next(
                (i + 1 for i, (off, _, __) in enumerate(page_offsets) if off <= m.start()), 1
            ),
            "ocr_confidence": conf,
            "low_confidence": conf < 0.6,
        })
    return segments


# ── Per-segment evaluation ───────────────────────────────────────────────────
def _evaluate_segment(seg: Dict, q_meta: Optional[Dict], subject: str, max_marks: int) -> Dict:
    q_text    = (q_meta or {}).get("question", "") or f"Question {seg['q_number']}"
    ref_answer = (q_meta or {}).get("reference_answer", "")
    q_type    = (q_meta or {}).get("type") or classify_question_type(q_text + " " + seg["text"])
    student_text = seg["text"]

    ocr_conf = seg.get("ocr_confidence", 1.0)
    # When OCR confidence is low the extracted text is unreliable; scale scores
    # down so garbled text doesn't inflate marks. No penalty above 0.70.
    ocr_penalty = min(1.0, ocr_conf / 0.70) if ocr_conf < 0.70 else 1.0

    result: Dict[str, Any] = {
        "q_number":       seg["q_number"],
        "q_type":         q_type,
        "question":       q_text,
        "ocr_text":       student_text,
        "ocr_confidence": round(ocr_conf, 3),
        "low_confidence": seg.get("low_confidence", False),
        "image_paths":    seg.get("image_paths", []),
        "page_start":     seg.get("page_start", 1),
    }

    try:
        if q_type == "drawing":
            img_path = seg["image_paths"][0] if seg.get("image_paths") else None
            ev = _drawing()(
                image_path=img_path,
                max_marks=max_marks,
                question=q_text,
                expected_parts=None,
                expected_dimensions=None,
            )
            raw_score = round(ev["ai_score"] * ocr_penalty, 1)
            result.update({
                "ai_score":              raw_score,
                "max_score":             ev["max_score"],
                "confidence":            round(ev.get("confidence", 0.5) * ocr_penalty, 2),
                "feedback":              ev.get("feedback", ""),
                "detection_mode":        ev.get("detection_mode", "ocr_text"),
                "requires_faculty_review": ev.get("requires_faculty_review", True),
                "is_stub":               False,
                "detail": {
                    "detected_elements": ev.get("detected_elements", []),
                    "matched_parts":     ev.get("matched_parts", []),
                    "missing_parts":     ev.get("missing_parts", []),
                    "matched_dimensions":ev.get("matched_dimensions", []),
                    "missing_dimensions":ev.get("missing_dimensions", []),
                    "deductions":        ev.get("deductions", []),
                    "ocr_text":          ev.get("ocr_text", ""),
                    "violations":        [],
                },
            })

        elif q_type == "numerical":
            ev = _numerical()(
                question=q_text,
                student_solution=student_text,
                reference_answer=ref_answer,
                rubric_steps=(q_meta or {}).get("rubric_steps", []),
                expected_formula=(q_meta or {}).get("expected_formula", ""),
                expected_final_answer=(q_meta or {}).get("expected_final_answer", ""),
                subject=subject,
                max_marks=max_marks,
            )
            raw_score = round(ev["ai_score"] * ocr_penalty, 1)
            result.update({
                "ai_score":   raw_score,
                "max_score":  ev["max_score"],
                "confidence": round(ev.get("confidence", 0.7) * ocr_penalty, 2),
                "feedback":   ev.get("feedback", ""),
                "detail": {
                    "steps":               ev.get("steps", []),
                    "error_summary":       ev.get("error_summary", {}),
                    "formula_mentioned":   ev.get("formula_mentioned", False),
                    "final_answer_correct":ev.get("final_answer_correct", False),
                    "deductions":          ev.get("deductions", []),
                },
            })

        else:  # theory
            # If no reference answer available, flag for faculty review
            # and give a neutral low score rather than inflating via embeddings
            if not ref_answer.strip():
                result.update({
                    "ai_score":   0,
                    "max_score":  max_marks,
                    "confidence": 0.0,
                    "feedback":   "No reference answer available — requires faculty review.",
                    "requires_faculty_review": True,
                    "detail": {},
                })
            else:
                ev = _theory()(
                    question=q_text,
                    student_answer=student_text,
                    reference_answer=ref_answer,
                    subject=subject,
                    max_marks=max_marks,
                )
                raw_score = round(ev["ai_score"] * ocr_penalty, 1)
                result.update({
                    "ai_score":   raw_score,
                    "max_score":  ev["max_score"],
                    "confidence": round(ev.get("confidence", 0.75) * ocr_penalty, 2),
                    "feedback":   ev.get("feedback", ""),
                    "detail": {
                        "keyword_score":    ev.get("keyword_score", 0),
                        "semantic_score":   ev.get("semantic_score", 0),
                        "matched_keywords": ev.get("keywords", {}).get("found", []),
                        "missing_keywords": ev.get("keywords", {}).get("missing", []),
                        "explanation":      ev.get("explanation", ""),
                    },
                })

    except Exception as exc:
        result.update({
            "ai_score":   0,
            "max_score":  max_marks,
            "confidence": 0.0,
            "feedback":   f"Evaluation error: {exc}",
            "detail": {},
        })

    return result


# ── Single-script entry point ────────────────────────────────────────────────
def evaluate_answer_script(
    file_path: str,
    subject: str = "Mechanical Engineering",
    max_marks_per_q: int = 10,
    exam_questions: Optional[List[Dict]] = None,
    student_name: str = "",
    student_usn: str = "",
) -> Dict:
    """
    Main pipeline for one answer script.
    Returns full JSON report: total_score, percentage, per-question detail, etc.
    """
    deps = get_dependency_status()

    is_pdf = file_path.lower().endswith(".pdf")
    if is_pdf:
        pages = ocr_pdf(file_path)
    else:
        pages = ocr_image_file(file_path)

    segments = segment_answers(pages)

    q_map: Dict[int, Dict] = {}
    if exam_questions:
        for q in exam_questions:
            q_map[int(q.get("q_number", 0))] = q

    answers = []
    total_score = 0.0
    max_total   = 0.0
    for seg in segments:
        q_meta = q_map.get(seg["q_number"])
        marks  = int((q_meta or {}).get("max_marks", max_marks_per_q))
        res    = _evaluate_segment(seg, q_meta, subject, marks)
        answers.append(res)
        total_score += res.get("ai_score", 0)
        max_total   += res.get("max_score", marks)

    percentage = round((total_score / max_total * 100), 1) if max_total > 0 else 0.0

    # Page-level OCR quality summary
    avg_ocr_conf = (
        sum(p.get("confidence", 1.0) for p in pages) / len(pages) if pages else 1.0
    )
    low_conf_pages = [p["page"] for p in pages if p.get("low_confidence")]

    return {
        "student_name":          student_name,
        "student_usn":           student_usn,
        "total_score":           round(total_score, 1),
        "max_total":             max_total,
        "percentage":            percentage,
        "subject":               subject,
        "questions_evaluated":   len(answers),
        "ocr_pages":             len(pages),
        "avg_ocr_confidence":    round(avg_ocr_conf, 3),
        "low_confidence_pages":  low_conf_pages,
        "ocr_warning":           len(low_conf_pages) > 0,
        "deps":                  deps,
        "answers":               answers,
    }


# ── Batch entry point ────────────────────────────────────────────────────────
def evaluate_multiple_scripts(
    file_entries: List[Dict],  # [{file_path, student_name, student_usn}, ...]
    subject: str = "Mechanical Engineering",
    max_marks_per_q: int = 10,
    exam_questions: Optional[List[Dict]] = None,
) -> Dict:
    """
    Batch evaluation: process multiple answer scripts.
    Returns {reports: [...], class_avg, pass_count, fail_count, ...}
    """
    reports = []
    for entry in file_entries:
        try:
            r = evaluate_answer_script(
                file_path=entry["file_path"],
                subject=subject,
                max_marks_per_q=max_marks_per_q,
                exam_questions=exam_questions,
                student_name=entry.get("student_name", ""),
                student_usn=entry.get("student_usn", ""),
            )
            r["error"] = None
        except Exception as exc:
            r = {
                "student_name": entry.get("student_name", ""),
                "student_usn":  entry.get("student_usn", ""),
                "file_path":    entry.get("file_path", ""),
                "error":        str(exc),
                "total_score":  0,
                "max_total":    0,
                "percentage":   0,
                "answers":      [],
            }
        reports.append(r)

    valid = [r for r in reports if not r.get("error")]
    class_avg = round(sum(r["percentage"] for r in valid) / len(valid), 1) if valid else 0.0
    pass_count = sum(1 for r in valid if r["percentage"] >= 40)
    fail_count = len(valid) - pass_count

    return {
        "reports":    reports,
        "total_students": len(reports),
        "class_avg":  class_avg,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "subject":    subject,
    }
