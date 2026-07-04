"""
Stage 5 — Confidence engine
===========================
Weighted overall confidence per answer:

  OCR confidence            30%
  Model (grader) confidence 30%
  Rubric coverage           15%   (fraction of rubric criteria the grader addressed)
  Semantic match certainty  15%   (how sure we are this answer belongs to this question)
  Answer completeness       10%

Rules:
  • overall < REVIEW_THRESHOLD (default 0.80)  → needs_faculty_review
  • OCR confidence < ILLEGIBLE_THRESHOLD        → illegible: no final marks,
    forced faculty review
"""

from __future__ import annotations
from typing import Dict

from evaluation.engine.config import get_config


def score_confidence(answer: Dict) -> Dict:
    """Mutates+returns answer with confidence fields and review flags."""
    cfg = get_config()

    ocr = float(answer.get("ocr_confidence", 1.0))
    model = float(answer.get("model_confidence", 0.6))

    mapping = answer.get("rubric_mapping") or []
    rubric_cov = (
        sum(1 for r in mapping if (r.get("reason") or "").strip()) / len(mapping)
        if mapping else 0.5
    )

    match_sim = answer.get("match_similarity")
    if answer.get("matched_by") == "detected_number":
        match_cert = 1.0
    elif match_sim is not None:
        match_cert = float(match_sim)
    else:
        match_cert = 0.5

    text_len = len((answer.get("ocr_text") or "").strip())
    completeness = min(1.0, text_len / 300.0)

    overall = round(
        0.30 * ocr + 0.30 * model + 0.15 * rubric_cov + 0.15 * match_cert + 0.10 * completeness,
        3,
    )

    illegible = ocr < cfg.illegible_ocr_threshold and text_len < 60
    needs_review = illegible or overall < cfg.review_confidence_threshold

    answer.update({
        "confidence": overall,
        "confidence_breakdown": {
            "ocr": round(ocr, 3),
            "model": round(model, 3),
            "rubric_coverage": round(rubric_cov, 3),
            "match_certainty": round(match_cert, 3),
            "completeness": round(completeness, 3),
        },
        "illegible": illegible,
        "requires_faculty_review": needs_review,
    })

    if illegible:
        # do not auto-assign final marks for illegible answers
        answer["ai_score_provisional"] = answer.get("ai_score", 0)
        answer["ai_score"] = 0.0
        answer["feedback"] = (
            "Handwriting could not be read reliably (OCR confidence "
            f"{ocr:.0%}). Marked for faculty review — no marks auto-assigned. "
            + (answer.get("feedback") or "")
        )
    return answer
