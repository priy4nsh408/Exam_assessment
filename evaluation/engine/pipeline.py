"""
Pipeline orchestrator
=====================
evaluate_script(file_path, exam) → full explainable report.

Two grading paths:
  1. VISION (primary, when a vision API key is set) — page images go straight
     to a vision model that reads the handwriting AND grades against the scheme
     in one call. Handles shuffled order, diagrams, equations, blank pages.
  2. OCR (fallback, no key) — Tesseract/PyMuPDF text extraction → segment →
     rubric grading with keyword+semantic scoring.

exam dict (all optional except questions for best results):
  {
    "subject": str, "semester": str, "exam_name": str, "max_marks": int,
    "marking_instructions": str,
    "questions": [
        {"q_number": int, "question": str, "reference_answer": str,
         "max_marks": float, "type": str, "rubric": [{"criterion","marks"}],
         "marking_instructions": str}
    ]
  }
"""

from __future__ import annotations
from typing import Dict, List, Optional

from evaluation.engine.ocr import ocr_document, page_images, dependency_status
from evaluation.engine.segment import segment_script
from evaluation.engine.detect import classify_question_type
from evaluation.engine.evaluate import evaluate_answer
from evaluation.engine.confidence import score_confidence
from evaluation.engine.vision_eval import vision_available, grade_script_vision


def _qn(q) -> int:
    try:
        return int(q.get("q_number") or 0)
    except (TypeError, ValueError):
        return 0


def evaluate_script(
    file_path: str,
    exam: Optional[Dict] = None,
    student_name: str = "",
    student_usn: str = "",
    max_marks_per_q: int = 10,
) -> Dict:
    import evaluation.engine.vision_eval as _ve

    exam = exam or {}
    subject = exam.get("subject") or "Mechanical Engineering"
    scheme: List[Dict] = exam.get("questions") or []

    # Choose path: vision when a key is set AND we have a scheme to grade against.
    has_key = _ve.vision_available()
    use_vision = has_key and bool(scheme)
    note = ""

    if use_vision:
        answers, pages_meta, method = _run_vision(file_path, exam)
        if answers is None:            # vision failed at runtime → fall back
            use_vision = False
            note = (f"Vision grading failed and fell back to OCR. Reason: "
                    f"{_ve.LAST_ERROR or 'unknown error'}. Click 'Test API key' to diagnose.")

    if not use_vision:
        answers, pages_meta, method = _run_ocr(file_path, exam, subject, max_marks_per_q)
        if not note:
            if not has_key:
                note = ("Handwriting could not be read: no vision AI was detected (no API key, and no "
                        "local Ollama vision model running), so Tesseract OCR was used — it cannot read "
                        "handwriting reliably. Fix options: set GEMINI_API_KEY in a .env file at the "
                        "project root, OR install Ollama and run 'ollama pull llava' for a fully offline, "
                        "no-API-key option — restart the backend after either. Or use the 'Paste Answers' "
                        "tab to grade typed/pasted text right now.")
            elif not scheme:
                note = ("No answer scheme was selected, so there was nothing to grade against. "
                        "Pick a reference scheme and re-run.")

    report = _assemble(answers, pages_meta, method, exam, scheme,
                       subject, max_marks_per_q, student_name, student_usn)
    report["grading_note"] = note
    report["vision_key_detected"] = has_key
    return report


# ── Path 1: vision ────────────────────────────────────────────────────────────

def _run_vision(file_path: str, exam: Dict):
    imgs = page_images(file_path)                       # [{page,image_path,blank}]
    live = [p for p in imgs if not p.get("blank")]
    records = grade_script_vision([p["image_path"] for p in live], exam)
    if records is None:
        return None, imgs, "vision"
    # attach confidence flags (never changes marks)
    answers = [score_confidence(r) for r in records]
    return answers, imgs, "vision"


# ── Path 3: typed / pasted text (always works, no OCR, no API) ────────────────

def evaluate_typed(
    exam: Dict,
    typed_answers: List[Dict],   # [{q_number, text}]
    student_name: str = "",
    student_usn: str = "",
    max_marks_per_q: int = 10,
) -> Dict:
    """
    Grade answers whose text is provided directly (pasted by faculty, or a
    typed PDF). No OCR, no vision — guaranteed to produce marks against the
    scheme. Uses the LLM grader if reachable, else the semantic fallback.
    """
    scheme = exam.get("questions") or []
    subject = exam.get("subject") or "Mechanical Engineering"
    global_instructions = exam.get("marking_instructions", "")
    q_map = {_qn(q): q for q in scheme}

    answers: List[Dict] = []
    for ta in typed_answers:
        try:
            qn = int(ta.get("q_number"))
        except (TypeError, ValueError):
            continue
        text = (ta.get("text") or "").strip()
        if not text:
            continue
        meta = q_map.get(qn, {}) or {}
        q_text = (meta.get("question") or "") or f"Question {qn}"
        ref = meta.get("reference_answer") or ""
        marks = float(meta.get("max_marks") or max_marks_per_q)
        q_type = classify_question_type(q_text, text, declared=meta.get("type") or "")
        instructions = " ".join(
            x for x in (global_instructions or "", meta.get("marking_instructions") or "") if x
        ).strip()

        graded = evaluate_answer(
            q_number=qn, q_type=q_type, question=q_text,
            student_answer=text, reference_answer=ref,
            max_marks=marks, rubric=meta.get("rubric"),
            subject=subject, marking_instructions=instructions,
        )
        record = {
            "q_number": qn, "q_type": q_type, "question": q_text,
            "ocr_text": text, "ocr_confidence": 1.0, "low_confidence": False,
            "image_paths": [], "page_start": 1,
            "matched_by": "manual", "match_similarity": None,
            **graded,
        }
        answers.append(score_confidence(record))

    return _assemble(answers, [], "manual", exam, scheme,
                     subject, max_marks_per_q, student_name, student_usn)


# ── Path 2: OCR fallback ──────────────────────────────────────────────────────

def _run_ocr(file_path: str, exam: Dict, subject: str, max_marks_per_q: int):
    scheme = exam.get("questions") or []
    global_instructions = exam.get("marking_instructions", "")
    pages = ocr_document(file_path)
    segments = segment_script(pages, scheme_questions=scheme or None)
    q_map = {_qn(q): q for q in scheme}

    answers: List[Dict] = []
    for seg in segments:
        q_meta = q_map.get(seg["q_number"], {}) or {}
        q_text = (q_meta.get("question") or "") or f"Question {seg['q_number']}"
        ref = q_meta.get("reference_answer") or ""
        marks = float(q_meta.get("max_marks") or max_marks_per_q)
        q_type = classify_question_type(q_text, seg["text"], declared=q_meta.get("type") or "")
        instructions = " ".join(
            x for x in (global_instructions or "", q_meta.get("marking_instructions") or "") if x
        ).strip()

        graded = evaluate_answer(
            q_number=seg["q_number"], q_type=q_type, question=q_text,
            student_answer=seg["text"], reference_answer=ref,
            max_marks=marks, rubric=q_meta.get("rubric"),
            subject=subject, marking_instructions=instructions,
        )
        record = {
            "q_number": seg["q_number"],
            "q_type": q_type,
            "question": q_text,
            "ocr_text": seg["text"],
            "ocr_confidence": round(seg.get("ocr_confidence", 1.0), 3),
            "low_confidence": seg.get("low_confidence", False),
            "image_paths": seg.get("image_paths", []),
            "page_start": seg.get("page_start", 1),
            "matched_by": seg.get("matched_by", ""),
            "match_similarity": seg.get("match_similarity"),
            "math_expressions": seg.get("math_expressions", []),
            "diagram_refs": seg.get("diagram_refs", []),
            **graded,
        }
        answers.append(score_confidence(record))
    return answers, pages, "ocr"


# ── Shared aggregation ────────────────────────────────────────────────────────

def _assemble(answers, pages_meta, method, exam, scheme,
              subject, max_marks_per_q, student_name, student_usn) -> Dict:
    blank_pages = [p["page"] for p in pages_meta if p.get("blank")]
    live_pages = [p for p in pages_meta if not p.get("blank")]

    # Unanswered scheme questions → listed explicitly (0 marks, no hallucination)
    answered_qs = {a["q_number"] for a in answers if not (a.get("attempted") is False)}
    unanswered = []
    for q in scheme:
        qn = _qn(q)
        if qn and qn not in answered_qs:
            unanswered.append({
                "q_number": qn, "question": q.get("question") or "",
                "max_marks": float(q.get("max_marks", max_marks_per_q)),
            })

    total = round(sum(a.get("ai_score", 0) for a in answers), 1)
    if scheme:
        max_total = float(exam.get("max_marks") or
                          sum(float(q.get("max_marks", max_marks_per_q)) for q in scheme))
    else:
        max_total = sum(a.get("max_score", max_marks_per_q) for a in answers)

    if method == "vision":
        avg_conf = round(sum(a.get("ocr_confidence", 0.85) for a in answers) / len(answers), 3) if answers else 0.9
        methods = sorted({a.get("grading_method", "vision") for a in answers})
    else:
        confs = [p.get("confidence", 1.0) for p in live_pages]
        avg_conf = round(sum(confs) / len(confs), 3) if confs else 1.0
        methods = sorted({p.get("method", "") for p in live_pages})

    review_qs = [a["q_number"] for a in answers if a.get("requires_faculty_review")]

    return {
        "student_name": student_name,
        "student_usn": student_usn,
        "subject": subject,
        "exam_name": exam.get("exam_name", ""),
        "semester": exam.get("semester", ""),
        "total_score": total,
        "max_total": max_total,
        "percentage": round(total / max_total * 100, 1) if max_total else 0.0,
        "questions_evaluated": len(answers),
        "grading_path": method,
        "ocr_pages": len(pages_meta),
        "blank_pages": blank_pages,
        "avg_ocr_confidence": avg_conf,
        "low_confidence_pages": [p["page"] for p in live_pages if p.get("low_confidence")],
        "ocr_warning": any(a.get("low_confidence") for a in answers) if method == "vision"
                       else any(p.get("low_confidence") for p in live_pages),
        "ocr_methods": methods,
        "needs_review_questions": review_qs,
        "unanswered_questions": unanswered,
        "deps": dependency_status(),
        "answers": answers,
        "overrides": [],
    }
