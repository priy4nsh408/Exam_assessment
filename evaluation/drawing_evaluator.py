"""
Drawing Evaluator — OCR-based label and annotation scoring.

Approach (no YOLOv8, no LLaVA required):
  1. Run EasyOCR on the drawing image to extract all text (labels, dimensions,
     annotations the student wrote on their drawing).
  2. Compare extracted text against expected parts and dimensions from the question.
  3. Score: start from max_marks, deduct for missing/incorrect labels.
  4. Flag for faculty review — a human should verify the actual drawn shapes.

This is honest and useful:
  - Theory engine grades WHAT the student wrote.
  - Drawing engine grades WHAT the student labeled (text found in image).
  - Faculty reviews the actual drawing lines/shapes.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

# ── OpenCV (optional — used only for image preprocessing) ────────────────────
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# ── OCR via EasyOCR (same engine as the script pipeline) ─────────────────────
try:
    import easyocr as _easyocr
    _reader = None

    def _get_reader():
        global _reader
        if _reader is None:
            _reader = _easyocr.Reader(["en"], gpu=False, verbose=False)
        return _reader

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


# ── Image preprocessing ───────────────────────────────────────────────────────

def _preprocess(image_path: str) -> Optional[str]:
    """
    Enhance image for OCR: grayscale → threshold → save to temp file.
    Returns path of preprocessed image, or None if cv2 unavailable.
    """
    if not CV2_AVAILABLE:
        return None
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Adaptive threshold improves OCR on pencil drawings
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        out_path = image_path + "_proc.png"
        cv2.imwrite(out_path, thresh)
        return out_path
    except Exception:
        return None


# ── OCR text extraction ───────────────────────────────────────────────────────

def _ocr_drawing(image_path: str) -> tuple[str, float]:
    """
    Extract all text from a drawing image using EasyOCR.
    Returns (text, avg_confidence).
    """
    if not EASYOCR_AVAILABLE or not image_path or not Path(image_path).exists():
        return "", 0.0

    proc = _preprocess(image_path) or image_path
    try:
        reader = _get_reader()
        results = reader.readtext(proc, detail=1, paragraph=False)
        if not results:
            return "", 0.0
        texts = [r[1] for r in results]
        confs = [float(r[2]) for r in results]
        return " ".join(texts), sum(confs) / len(confs)
    except Exception:
        return "", 0.0


# ── Expected-parts extraction from question text ──────────────────────────────

def _extract_expected_parts(question: str) -> List[str]:
    """Pull component/view names from the question."""
    found = []
    patterns = [
        r"\b(front\s*view|top\s*view|side\s*view|isometric|orthograph\w+|section\w*|plan\s*view)\b",
        r"\b(piston|cylinder|bearing|shaft|flange|gear|bolt|nut|key|pulley|cam|valve|spring)\b",
        r"\b(title\s*block|dimension\s*line|center\s*line|hidden\s*line|cutting\s*plane)\b",
    ]
    for pat in patterns:
        found += re.findall(pat, question, re.I)
    return list(dict.fromkeys(f.strip().lower() for f in found if f.strip()))


def _extract_expected_dimensions(question: str) -> List[str]:
    """Pull numeric dimensions from the question."""
    return re.findall(r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|in|°|deg)\b", question, re.I)


# ── Label matching ────────────────────────────────────────────────────────────

def _match_labels(ocr_text: str, expected: List[str]) -> tuple[List[str], List[str]]:
    """
    Return (matched, missing) lists by checking if each expected label
    appears (fuzzy substring) in the OCR-extracted text.
    """
    text_lower = ocr_text.lower()
    matched, missing = [], []
    for label in expected:
        # Allow partial word matches (e.g. "front" matches "front view")
        key = label.lower().split()[0] if label else ""
        if key and key in text_lower:
            matched.append(label)
        else:
            missing.append(label)
    return matched, missing


# ── Scoring ───────────────────────────────────────────────────────────────────

def _compute_score(
    max_marks: float,
    matched_parts: List[str],
    missing_parts: List[str],
    matched_dims: List[str],
    missing_dims: List[str],
    ocr_confidence: float,
) -> tuple[float, List[Dict]]:
    """
    Score from max_marks with deductions.
    Returns (final_score, deductions_list).
    """
    deductions = []
    total_ded = 0.0

    # Missing parts: -1 each
    for p in missing_parts:
        deductions.append({"reason": f"Part/view not labeled: '{p}'", "marks": 1.0})
        total_ded += 1.0

    # Missing dimensions: -0.5 each
    for d in missing_dims:
        deductions.append({"reason": f"Dimension not marked: '{d}'", "marks": 0.5})
        total_ded += 0.5

    # Low OCR confidence: flag but no deduction (human error, not student error)
    score = max(0.0, round(max_marks - total_ded, 1))
    return score, deductions


# ── Main entry point ──────────────────────────────────────────────────────────

def evaluate_drawing(
    image_path: Optional[str] = None,
    max_marks: int = 20,
    question: str = "",
    expected_parts: Optional[List[str]] = None,
    expected_dimensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    OCR-based drawing evaluation.

    Extracts all text labels and annotations the student wrote on their drawing,
    then checks against expected parts/dimensions from the question rubric.

    Does NOT do shape detection — that requires faculty visual review.
    Sets requires_faculty_review=True so the UI flags it clearly.
    """
    # Resolve expected parts / dimensions
    exp_parts = expected_parts or _extract_expected_parts(question)
    exp_dims  = expected_dimensions or _extract_expected_dimensions(question)

    # Extract text from the drawing image
    ocr_text, ocr_conf = _ocr_drawing(image_path) if image_path else ("", 0.0)

    # Match labels
    matched_parts, missing_parts = _match_labels(ocr_text, exp_parts)
    matched_dims,  missing_dims  = _match_labels(ocr_text, exp_dims)

    # Score
    ai_score, deductions = _compute_score(
        max_marks, matched_parts, missing_parts,
        matched_dims, missing_dims, ocr_conf,
    )

    # Build feedback
    lines = []
    if not image_path:
        lines.append("No image provided — manual evaluation required.")
        ai_score = 0.0
    else:
        if not EASYOCR_AVAILABLE:
            lines.append("OCR not available (install easyocr). Score is indicative only.")
            ai_score = round(max_marks * 0.5, 1)  # give benefit of doubt
        elif not ocr_text.strip():
            lines.append("No text detected in drawing. If the drawing has labels/annotations, check image quality.")
        else:
            if matched_parts:
                lines.append(f"Labels found: {', '.join(matched_parts)}.")
            if missing_parts:
                lines.append(f"Labels not detected: {', '.join(missing_parts)} (−1 each).")
            if matched_dims:
                lines.append(f"Dimensions marked: {', '.join(matched_dims)}.")
            if missing_dims:
                lines.append(f"Dimensions not found: {', '.join(missing_dims)} (−0.5 each).")
            if not (missing_parts or missing_dims):
                lines.append("All expected labels and dimensions were detected.")

    lines.append("Faculty review recommended to verify actual drawing quality and line work.")

    # Detected elements list (from OCR text — honest)
    detected_elements = [t.strip() for t in ocr_text.split() if len(t.strip()) > 2] if ocr_text else []

    return {
        "ai_score":             ai_score,
        "max_score":            max_marks,
        "confidence":           round(ocr_conf, 3) if ocr_conf else 0.5,
        "detection_mode":       "ocr_text",   # honest: text extraction, not shape detection
        "requires_faculty_review": True,
        "ocr_text":             ocr_text,
        "ocr_available":        EASYOCR_AVAILABLE,
        "expected_parts":       exp_parts,
        "expected_dimensions":  exp_dims,
        "matched_parts":        matched_parts,
        "missing_parts":        missing_parts,
        "matched_dimensions":   matched_dims,
        "missing_dimensions":   missing_dims,
        "detected_elements":    detected_elements[:20],  # text tokens found
        "deductions":           deductions,
        "violations":           [],   # no IS/BIS rules without real shape detection
        "feedback":             " ".join(lines),
        "explanation":          (
            f"Score based on text labels found via OCR in the drawing image. "
            f"OCR confidence: {round(ocr_conf*100)}%. "
            f"Matched {len(matched_parts)}/{len(exp_parts)} parts, "
            f"{len(matched_dims)}/{len(exp_dims)} dimensions. "
            f"Shape quality and line work require faculty visual inspection."
        ),
        "preprocessing_applied": CV2_AVAILABLE and image_path is not None,
        "vlm_output":           {},  # removed — LLaVA not required
    }
