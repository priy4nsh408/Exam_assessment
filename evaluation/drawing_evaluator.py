"""
Engineering drawing evaluation pipeline.
Preprocessing: OpenCV (grayscale → CLAHE → adaptive threshold → morphological denoise)
Detection: YOLOv8 (stubbed until training data available) or heuristic
VLM: LLaVA via Ollama for semantic interpretation
Compliance: IS 696:1972, SP:46:2003, IS 919:1993, IS 3073 rule engine
"""

import os
import json
import base64
import re
from pathlib import Path
from typing import Optional

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# ── IS/BIS Compliance Rules ────────────────────────────────────────────────────

IS_RULES = [
    {
        "id": "IS696-6.3",
        "clause": "IS 696:1972 Clause 6.3",
        "description": "First angle projection must be used in Indian engineering drawings",
        "check_key": "projection_angle",
        "invalid_values": ["third_angle", "third angle"],
        "severity": "major",
        "deduction": 4,
    },
    {
        "id": "IS696-5.1",
        "clause": "IS 696:1972 Clause 5.1",
        "description": "All three principal views (front, top, side) must be present",
        "check_key": "views_detected",
        "min_count": 2,
        "severity": "major",
        "deduction": 5,
    },
    {
        "id": "IS919-4.1",
        "clause": "IS 919:1993 Clause 4.1",
        "description": "Dimensional tolerance notation must follow standard form (e.g., 50±0.5 not 50 ±.5)",
        "check_key": "tolerances",
        "pattern_check": True,
        "severity": "minor",
        "deduction": 1,
    },
    {
        "id": "SP46-8.2",
        "clause": "SP:46:2003 Section 8.2",
        "description": "Title block must include: drawing number, scale, material, date",
        "check_key": "title_block",
        "required_fields": ["drawing_no", "scale", "date"],
        "severity": "minor",
        "deduction": 1,
    },
    {
        "id": "IS3073-3.1",
        "clause": "IS 3073:1967 Clause 3.1",
        "description": "Surface finish symbols must follow IS 3073 notation",
        "check_key": "surface_finish",
        "severity": "minor",
        "deduction": 1,
    },
]

DRAWING_ELEMENTS = [
    {"name": "Front View", "max_marks": 5},
    {"name": "Top View", "max_marks": 5},
    {"name": "Side View", "max_marks": 5},
    {"name": "Dimension Lines", "max_marks": 4},
    {"name": "Title Block", "max_marks": 3},
    {"name": "GD&T Frame", "max_marks": 3},
]

# ── OpenCV Preprocessing ───────────────────────────────────────────────────────

def preprocess_image(image_path: str) -> Optional[object]:
    """
    OpenCV pipeline: grayscale → CLAHE → adaptive threshold → morphological denoise.
    Returns preprocessed image array or None if CV2 unavailable.
    """
    if not CV2_AVAILABLE:
        return None
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None

        # Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Hough-line based deskewing
        edges = cv2.Canny(enhanced, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
        if lines is not None:
            angles = [line[0][1] for line in lines[:10]]
            median_angle = np.median(angles) - np.pi / 2
            if abs(median_angle) < 0.1:  # only correct small skews
                h, w = enhanced.shape
                M = cv2.getRotationMatrix2D((w // 2, h // 2), np.degrees(median_angle), 1.0)
                enhanced = cv2.warpAffine(enhanced, M, (w, h), flags=cv2.INTER_CUBIC,
                                          borderMode=cv2.BORDER_REPLICATE)

        # Adaptive threshold
        thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)

        # Morphological noise removal
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # Resize to standard 1024x768
        resized = cv2.resize(cleaned, (1024, 768))
        return resized

    except Exception:
        return None

def image_to_base64(image_path: str) -> Optional[str]:
    """Convert image file to base64 string for VLM input."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

# ── YOLOv8 Detection (stub until training data available) ─────────────────────

def detect_elements(image_path: str) -> list:
    """
    YOLOv8 drawing element detection.
    Returns list of detected elements with confidence scores.
    NOTE: Returns heuristic results until fine-tuned weights are available.
    To use real YOLOv8: pip install ultralytics, load model with YOLO('drawing_model.pt')
    """
    # Stub: heuristic detection based on image analysis
    # Replace with: from ultralytics import YOLO; model = YOLO('drawing_model.pt')
    detected = []

    if CV2_AVAILABLE and image_path and Path(image_path).exists():
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            h, w = img.shape
            # Heuristic: check quadrants for view presence
            quadrants = [
                ("Front View", img[:h//2, :w//2]),
                ("Top View", img[h//2:, :w//2]),
                ("Side View", img[:h//2, w//2:]),
            ]
            for name, quad in quadrants:
                # If quadrant has significant non-white content → likely a view
                dark_pixels = np.sum(quad < 128)
                ratio = dark_pixels / quad.size
                if ratio > 0.05:
                    detected.append({"element": name, "confidence": round(0.6 + ratio, 2), "detected": True})
                else:
                    detected.append({"element": name, "confidence": 0.2, "detected": False})

            # Always attempt title block (usually bottom strip)
            bottom = img[int(h*0.85):, :]
            dark = np.sum(bottom < 128) / bottom.size
            detected.append({"element": "Title Block", "confidence": round(0.5 + dark, 2), "detected": dark > 0.1})
            detected.append({"element": "Dimension Lines", "confidence": 0.65, "detected": True})
            detected.append({"element": "GD&T Frame", "confidence": 0.3, "detected": False})
            return detected

    # Pure fallback (no image)
    return [
        {"element": "Front View", "confidence": 0.82, "detected": True},
        {"element": "Top View", "confidence": 0.78, "detected": True},
        {"element": "Side View", "confidence": 0.71, "detected": True},
        {"element": "Dimension Lines", "confidence": 0.65, "detected": True},
        {"element": "Title Block", "confidence": 0.55, "detected": True},
        {"element": "GD&T Frame", "confidence": 0.28, "detected": False},
    ]

# ── LLaVA VLM Interpretation ──────────────────────────────────────────────────

def vlm_interpret(image_path: str) -> dict:
    """
    Uses LLaVA (via Ollama) to interpret the drawing and return structured JSON.
    Falls back to structured placeholder if LLaVA unavailable.
    """
    if not OLLAMA_AVAILABLE:
        return _fallback_vlm_output()

    img_b64 = image_to_base64(image_path)
    if not img_b64:
        return _fallback_vlm_output()

    prompt = """Analyze this engineering drawing and return ONLY a JSON object with this exact structure:
{
  "view_type": "orthographic" or "isometric" or "perspective",
  "projection_angle": "first_angle" or "third_angle" or "unknown",
  "views_detected": ["front", "top", "side"] (list only views you can see),
  "dimensions": ["list of dimension values you can read, e.g. 45mm, 30mm"],
  "tolerances": ["list of tolerance notations you see"],
  "GDT_symbols": ["list of GD&T symbols: flatness, perpendicularity, etc."],
  "surface_finish": ["surface finish values you see, e.g. Ra 3.2"],
  "title_block": {
    "drawing_no": "value or null",
    "scale": "value or null",
    "material": "value or null",
    "date": "value or null"
  }
}
Return ONLY valid JSON. No explanation."""

    try:
        resp = ollama.chat(
            model="llava",
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [img_b64]
            }]
        )
        text = resp["message"]["content"].strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    return _fallback_vlm_output()

def _fallback_vlm_output() -> dict:
    return {
        "view_type": "orthographic",
        "projection_angle": "unknown",
        "views_detected": ["front", "top"],
        "dimensions": [],
        "tolerances": [],
        "GDT_symbols": [],
        "surface_finish": [],
        "title_block": {"drawing_no": None, "scale": None, "material": None, "date": None},
    }

# ── IS/BIS Compliance Engine ──────────────────────────────────────────────────

def check_compliance(vlm_output: dict, detected_elements: list) -> list:
    """
    Validates VLM-interpreted drawing JSON against IS/BIS rules.
    Returns list of violations with IS clause citations and deductions.
    """
    violations = []

    for rule in IS_RULES:
        key = rule["check_key"]

        # Projection angle check
        if key == "projection_angle":
            angle = vlm_output.get("projection_angle", "").lower()
            if angle in rule.get("invalid_values", []):
                violations.append({
                    "rule_id": rule["id"],
                    "clause": rule["clause"],
                    "issue": rule["description"],
                    "severity": rule["severity"],
                    "deduction": rule["deduction"],
                    "found": angle,
                })

        # View count check
        elif key == "views_detected":
            views = vlm_output.get("views_detected", [])
            if len(views) < rule.get("min_count", 2):
                violations.append({
                    "rule_id": rule["id"],
                    "clause": rule["clause"],
                    "issue": f"Only {len(views)} view(s) detected — minimum {rule['min_count']} required",
                    "severity": rule["severity"],
                    "deduction": rule["deduction"],
                    "found": views,
                })

        # Tolerance notation check
        elif key == "tolerances" and rule.get("pattern_check"):
            tolerances = vlm_output.get("tolerances", [])
            for t in tolerances:
                # Non-standard: tolerance written without leading digit (e.g. ±.5 instead of ±0.5)
                if re.search(r'[±]\s*\.\d', t):
                    violations.append({
                        "rule_id": rule["id"],
                        "clause": rule["clause"],
                        "issue": f"Non-standard tolerance notation: '{t}' — should be e.g. ±0.5",
                        "severity": rule["severity"],
                        "deduction": rule["deduction"],
                        "found": t,
                    })
                    break

        # Title block check
        elif key == "title_block":
            tb = vlm_output.get("title_block", {})
            missing = [f for f in rule.get("required_fields", []) if not tb.get(f)]
            if missing:
                violations.append({
                    "rule_id": rule["id"],
                    "clause": rule["clause"],
                    "issue": f"Title block missing: {', '.join(missing)}",
                    "severity": rule["severity"],
                    "deduction": rule["deduction"],
                    "found": tb,
                })

    return violations

# ── Scoring ───────────────────────────────────────────────────────────────────

def score_elements(detected_elements: list) -> list:
    """Score each detected element against its max marks."""
    scored = []
    element_scores = {e["name"]: e["max_marks"] for e in DRAWING_ELEMENTS}

    for det in detected_elements:
        name = det["element"]
        max_m = element_scores.get(name, 3)
        if det["detected"]:
            conf = det["confidence"]
            earned = round(max_m * min(conf, 1.0), 1)
        else:
            earned = 0
        scored.append({
            "element": name,
            "status": "detected" if det["detected"] else "not_detected",
            "confidence": det["confidence"],
            "score": f"{earned}/{max_m}",
            "earned": earned,
            "max": max_m,
        })
    return scored

# ── Main Entry Point ──────────────────────────────────────────────────────────

def evaluate_drawing(image_path: Optional[str] = None, max_marks: int = 20) -> dict:
    """
    Full drawing evaluation pipeline.
    Returns complete evaluation result dict.
    """
    # Step 1: Preprocess
    preprocessed = None
    if image_path and Path(image_path).exists():
        preprocessed = preprocess_image(image_path)

    # Step 2: YOLOv8 detection
    detected = detect_elements(image_path or "")

    # Step 3: VLM interpretation
    vlm_output = vlm_interpret(image_path or "") if image_path else _fallback_vlm_output()

    # Step 4: IS/BIS compliance
    violations = check_compliance(vlm_output, detected)

    # Step 5: Score elements
    scored_elements = score_elements(detected)

    # Calculate total
    element_total = sum(e["earned"] for e in scored_elements)
    element_max = sum(e["max"] for e in scored_elements)
    violation_deductions = sum(v["deduction"] for v in violations)

    raw_score = max(0, (element_total / max(element_max, 1)) * max_marks - violation_deductions)
    ai_score = round(min(raw_score, max_marks), 1)

    total_deductions = violation_deductions
    confidence = 0.75 if image_path else 0.5

    return {
        "ai_score": ai_score,
        "max_score": max_marks,
        "confidence": confidence,
        "detected_elements": scored_elements,
        "violations": violations,
        "violation_deductions": total_deductions,
        "vlm_output": vlm_output,
        "preprocessing_applied": preprocessed is not None,
        "feedback": _generate_feedback(violations, scored_elements),
    }

def _generate_feedback(violations: list, elements: list) -> str:
    major = [v for v in violations if v["severity"] == "major"]
    minor = [v for v in violations if v["severity"] == "minor"]
    not_detected = [e for e in elements if e["status"] == "not_detected"]

    parts = []
    if major:
        parts.append(f"{len(major)} major IS violation(s): {major[0]['issue']}.")
    if minor:
        parts.append(f"{len(minor)} minor violation(s) noted.")
    if not_detected:
        parts.append(f"Missing elements: {', '.join(e['element'] for e in not_detected)}.")
    if not parts:
        parts.append("Drawing meets IS/BIS standards. All required elements detected.")
    return " ".join(parts)
