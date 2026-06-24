"""
Answer-Script Pipeline
======================
Orchestrates the full flow:
  PDF/image upload → OCR → answer segmentation → question-type classification
  → dispatch to theory / numerical / drawing evaluator → aggregate report

Public entry point:
  evaluate_answer_script(file_path, subject, max_marks_per_q, exam_questions)
"""

from __future__ import annotations
import re
from typing import List, Dict, Optional, Any

from evaluation.ocr_engine import ocr_pdf, ocr_image_file

# ── lazy imports so the module loads even without ML deps ────────────────────
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
    r"\b(calculat|comput|find|determin|evaluat|solv|what is the value|"
    r"how much|how many|express in|in units|mpa|kpa|kn|rpm|"
    r"stress|strain|force|moment|torque|velocity|pressure|"
    r"temperature|efficiency|power|energy|heat|work|"
    r"area|volume|length|diameter|radius)\b",
    re.I,
)
_DRAWING_SIGNALS = re.compile(
    r"\b(draw|sketch|illustrat|show (the|a)|diagram|label|mark|"
    r"cross.?section|isometric|orthograph|projection|free.?body|fbd|"
    r"shear force|bending moment|t.?s diagram|p.?v diagram)\b",
    re.I,
)
_THEORY_SIGNALS = re.compile(
    r"\b(explain|describe|define|state|list|discuss|differentiat|compare|"
    r"what (is|are|do)|how does|why|advantages|disadvantages|"
    r"principle|concept|law|theorem|classification|types of)\b",
    re.I,
)


def classify_question_type(text: str) -> str:
    """Return 'theory', 'numerical', or 'drawing' based on keyword signals."""
    scores = {
        "drawing": len(_DRAWING_SIGNALS.findall(text)),
        "numerical": len(_NUMERICAL_SIGNALS.findall(text)),
        "theory": len(_THEORY_SIGNALS.findall(text)),
    }
    return max(scores, key=scores.get)  # type: ignore[arg-type]


# ── Answer segmentation ──────────────────────────────────────────────────────

_ANSWER_BOUNDARY = re.compile(
    r"(?m)^[\s]*(?:"
    r"(?:ans(?:wer)?\.?\s*)?[Qq](?:uestion)?\.?\s*(\d+)"   # Q1, Question 1, Ans Q1
    r"|(\d+)[.)]\s"                                          # 1. or 1)
    r"|(?:ans(?:wer)?\.?\s*(\d+))"                          # Answer 3
    r")",
)


def segment_answers(pages: List[Dict]) -> List[Dict]:
    """
    Given per-page OCR results, detect answer boundaries and return a list of
    answer segments: {q_number, text, image_paths, page_start}.

    Falls back to one-segment-per-page when no explicit markers are found.
    """
    full_text = ""
    page_offsets: List[tuple[int, str]] = []  # (char_offset, image_path)
    for p in pages:
        page_offsets.append((len(full_text), p["image_path"]))
        full_text += p["text"] + "\n\n"

    matches = list(_ANSWER_BOUNDARY.finditer(full_text))

    def _q_num(m: re.Match) -> int:
        return int(next(g for g in m.groups() if g is not None))

    def _img_for_offset(offset: int) -> str:
        img = page_offsets[0][1]
        for char_off, path in page_offsets:
            if char_off <= offset:
                img = path
        return img

    if not matches:
        # No markers — treat each page as a separate answer
        segments = []
        for i, p in enumerate(pages, start=1):
            segments.append({
                "q_number": i,
                "text": p["text"],
                "image_paths": [p["image_path"]],
                "page_start": p["page"],
            })
        return segments

    segments: List[Dict] = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        img = _img_for_offset(m.start())
        segments.append({
            "q_number": _q_num(m),
            "text": full_text[start:end].strip(),
            "image_paths": [img],
            "page_start": next(
                (i + 1 for i, (off, _) in enumerate(page_offsets) if off <= m.start()),
                1,
            ),
        })
    return segments


# ── Per-question evaluator dispatch ─────────────────────────────────────────

def _evaluate_segment(
    seg: Dict,
    q_meta: Optional[Dict],
    subject: str,
    max_marks: int,
) -> Dict:
    """Route one answer segment to the right evaluator and return its result."""
    q_text = (q_meta or {}).get("question", "") or f"Question {seg['q_number']}"
    ref_answer = (q_meta or {}).get("reference_answer", "")
    q_type = (q_meta or {}).get("type") or classify_question_type(q_text + " " + seg["text"])
    student_text = seg["text"]

    result: Dict[str, Any] = {
        "q_number": seg["q_number"],
        "q_type": q_type,
        "question": q_text,
        "ocr_text": student_text,
        "image_paths": seg.get("image_paths", []),
        "page_start": seg.get("page_start", 1),
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
            result.update({
                "ai_score": ev["ai_score"],
                "max_score": ev["max_score"],
                "confidence": ev.get("confidence", 0.6),
                "feedback": ev.get("feedback", ""),
                "detail": {
                    "detected_elements": ev.get("detected_elements", []),
                    "violations": ev.get("violations", []),
                    "rubric": ev.get("rubric", []),
                },
            })

        elif q_type == "numerical":
            rubric = (q_meta or {}).get("rubric_steps", [])
            ev = _numerical()(
                question=q_text,
                student_solution=student_text,
                reference_answer=ref_answer,
                rubric_steps=rubric,
                expected_formula=(q_meta or {}).get("expected_formula", ""),
                expected_final_answer=(q_meta or {}).get("expected_final_answer", ""),
                subject=subject,
                max_marks=max_marks,
            )
            result.update({
                "ai_score": ev["ai_score"],
                "max_score": ev["max_score"],
                "confidence": ev.get("confidence", 0.7),
                "feedback": ev.get("feedback", ""),
                "detail": {
                    "steps": ev.get("steps", []),
                    "error_summary": ev.get("error_summary", {}),
                    "formula_mentioned": ev.get("formula_mentioned", False),
                    "final_answer_correct": ev.get("final_answer_correct", False),
                    "deductions": ev.get("deductions", []),
                },
            })

        else:  # theory
            ev = _theory()(
                question=q_text,
                student_answer=student_text,
                reference_answer=ref_answer,
                subject=subject,
                max_marks=max_marks,
            )
            result.update({
                "ai_score": ev["ai_score"],
                "max_score": ev["max_score"],
                "confidence": ev.get("confidence", 0.75),
                "feedback": ev.get("feedback", ""),
                "detail": {
                    "keyword_score": ev.get("keyword_score", 0),
                    "semantic_score": ev.get("semantic_score", 0),
                    "matched_keywords": ev.get("keywords", {}).get("found", []),
                    "missing_keywords": ev.get("keywords", {}).get("missing", []),
                    "explanation": ev.get("explanation", ""),
                },
            })

    except Exception as exc:
        result.update({
            "ai_score": 0,
            "max_score": max_marks,
            "confidence": 0.0,
            "feedback": f"Evaluation error: {exc}",
            "detail": {},
        })

    return result


# ── Public entry point ────────────────────────────────────────────────────────

def evaluate_answer_script(
    file_path: str,
    subject: str = "Mechanical Engineering",
    max_marks_per_q: int = 10,
    exam_questions: Optional[List[Dict]] = None,
) -> Dict:
    """
    Main pipeline.

    Parameters
    ----------
    file_path       : absolute path to uploaded PDF or image
    subject         : subject name passed to evaluators
    max_marks_per_q : marks per question (uniform; override via exam_questions)
    exam_questions  : optional list of dicts with keys:
                      q_number, question, type, reference_answer, max_marks,
                      expected_formula, expected_final_answer, rubric_steps

    Returns
    -------
    {
      total_score, max_total, percentage, subject,
      questions_evaluated, ocr_pages,
      answers: [ per-question result dicts ]
    }
    """
    is_pdf = file_path.lower().endswith(".pdf")
    if is_pdf:
        pages = ocr_pdf(file_path)
    else:
        pages = ocr_image_file(file_path)

    segments = segment_answers(pages)

    # Build a lookup {q_number -> question metadata} from optional exam_questions
    q_map: Dict[int, Dict] = {}
    if exam_questions:
        for q in exam_questions:
            q_map[int(q.get("q_number", 0))] = q

    answers = []
    total_score = 0.0
    max_total = 0.0
    for seg in segments:
        q_meta = q_map.get(seg["q_number"])
        marks = int((q_meta or {}).get("max_marks", max_marks_per_q))
        res = _evaluate_segment(seg, q_meta, subject, marks)
        answers.append(res)
        total_score += res.get("ai_score", 0)
        max_total += res.get("max_score", marks)

    percentage = round((total_score / max_total * 100), 1) if max_total > 0 else 0.0

    return {
        "total_score": round(total_score, 1),
        "max_total": max_total,
        "percentage": percentage,
        "subject": subject,
        "questions_evaluated": len(answers),
        "ocr_pages": len(pages),
        "answers": answers,
    }
