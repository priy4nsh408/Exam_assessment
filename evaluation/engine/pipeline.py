"""
Pipeline orchestrator
=====================
evaluate_script(file_path, exam) → full explainable report.

exam dict (all optional except questions for best results):
  {
    "subject": str, "semester": str, "exam_name": str, "max_marks": int,
    "marking_instructions": str,          # global numerical/diagram instructions
    "questions": [
        {"q_number": int, "question": str, "reference_answer": str,
         "max_marks": float, "type": str, "rubric": [{"criterion","marks"}],
         "marking_instructions": str}
    ]
  }
"""

from __future__ import annotations
from typing import Dict, List, Optional

from evaluation.engine.ocr import ocr_document, dependency_status
from evaluation.engine.segment import segment_script
from evaluation.engine.detect import classify_question_type
from evaluation.engine.evaluate import evaluate_answer
from evaluation.engine.confidence import score_confidence


def evaluate_script(
    file_path: str,
    exam: Optional[Dict] = None,
    student_name: str = "",
    student_usn: str = "",
    max_marks_per_q: int = 10,
) -> Dict:
    exam = exam or {}
    subject = exam.get("subject") or "Mechanical Engineering"
    scheme: List[Dict] = exam.get("questions") or []
    global_instructions = exam.get("marking_instructions", "")

    # 1. OCR (blank pages auto-flagged, never evaluated)
    pages = ocr_document(file_path)
    blank_pages = [p["page"] for p in pages if p.get("blank")]
    live_pages = [p for p in pages if not p.get("blank")]

    # 2+3. Detect + segment + semantic match to scheme
    segments = segment_script(pages, scheme_questions=scheme or None)

    q_map = {int(q.get("q_number", 0)): q for q in scheme}

    # 4. Evaluate every segment
    answers: List[Dict] = []
    for seg in segments:
        q_meta = q_map.get(seg["q_number"], {})
        q_text = q_meta.get("question", "") or f"Question {seg['q_number']}"
        ref = q_meta.get("reference_answer", "")
        marks = float(q_meta.get("max_marks", max_marks_per_q) or max_marks_per_q)
        q_type = classify_question_type(q_text, seg["text"], declared=q_meta.get("type", ""))
        instructions = " ".join(x for x in (global_instructions, q_meta.get("marking_instructions", "")) if x).strip()

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

    # Unanswered scheme questions → 0 marks, listed explicitly (no hallucination)
    answered_qs = {a["q_number"] for a in answers}
    unanswered = []
    for q in scheme:
        qn = int(q.get("q_number", 0))
        if qn and qn not in answered_qs:
            unanswered.append({
                "q_number": qn, "question": q.get("question", ""),
                "max_marks": float(q.get("max_marks", max_marks_per_q)),
            })

    # 6. Aggregate
    total = round(sum(a.get("ai_score", 0) for a in answers), 1)
    if scheme:
        max_total = float(exam.get("max_marks") or sum(float(q.get("max_marks", max_marks_per_q)) for q in scheme))
    else:
        max_total = sum(a.get("max_score", max_marks_per_q) for a in answers)

    live_confs = [p.get("confidence", 1.0) for p in live_pages]
    avg_ocr = round(sum(live_confs) / len(live_confs), 3) if live_confs else 1.0
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
        "ocr_pages": len(pages),
        "blank_pages": blank_pages,
        "avg_ocr_confidence": avg_ocr,
        "low_confidence_pages": [p["page"] for p in live_pages if p.get("low_confidence")],
        "ocr_warning": any(p.get("low_confidence") for p in live_pages),
        "ocr_methods": sorted({p.get("method", "") for p in live_pages}),
        "needs_review_questions": review_qs,
        "unanswered_questions": unanswered,
        "deps": dependency_status(),
        "answers": answers,
        "overrides": [],
    }
