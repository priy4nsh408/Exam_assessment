"""
Stage 5 — Confidence annotation (informational only)
====================================================
The answer scheme is the master. Marks come from the grading stage — they are
NEVER overridden here. This stage only attaches a confidence number and a
"you may want to double-check this one" flag for the faculty review queue.

  overall < REVIEW_THRESHOLD (default 0.80)  → requires_faculty_review = True
                                               (a hint, NOT a marks change)

Marks are always kept exactly as the grader awarded them. Faculty override
handles any corrections.
"""

from __future__ import annotations
from typing import Dict

from evaluation.engine.config import get_config


def score_confidence(answer: Dict) -> Dict:
    """Attach confidence + review flag. Never changes ai_score."""
    cfg = get_config()

    ocr = float(answer.get("ocr_confidence", 1.0))
    model = float(answer.get("model_confidence", 0.6))

    mapping = answer.get("rubric_mapping") or []
    rubric_cov = (
        sum(1 for r in mapping if (r.get("reason") or "").strip()) / len(mapping)
        if mapping else 0.5
    )

    match_sim = answer.get("match_similarity")
    if answer.get("matched_by") in ("detected_number", "vision"):
        match_cert = 1.0            # the model / an explicit number matched it
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

    # Low OCR confidence is just a hint to double-check the handwriting reading.
    # It does NOT withhold marks — the grade against the scheme stands.
    hard_to_read = ocr < cfg.illegible_ocr_threshold and text_len < 40

    # Review is a genuine "the grader was unsure" signal, not a default. Flag
    # only when the model itself is not confident, or the reading was poor —
    # NOT just because an answer is short. Marks always stand regardless.
    needs_review = hard_to_read or model < 0.55 or ocr < 0.45

    answer.update({
        "confidence": overall,
        "confidence_breakdown": {
            "ocr": round(ocr, 3),
            "model": round(model, 3),
            "rubric_coverage": round(rubric_cov, 3),
            "match_certainty": round(match_cert, 3),
            "completeness": round(completeness, 3),
        },
        "illegible": hard_to_read,
        "requires_faculty_review": needs_review,
    })
    return answer
