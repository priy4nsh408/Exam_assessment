"""
Engineering drawing evaluation pipeline.
Preprocessing: OpenCV (grayscale → CLAHE → adaptive threshold → morphological denoise)
Detection: YOLOv8 (stubbed until training data available) or heuristic
VLM: LLaVA via Ollama for semantic interpretation
Compliance: IS 696:1972, SP:46:2003, IS 919:1993, IS 3073 rule engine

Marking rubric (as specified):
  - Missing dimension marking  -> -0.5 mark each
  - Missing diagram part/block (e.g. a labeled component of a block
    diagram) -> -1 mark each
  - Dimension present but wrong value, when the question specifies the
    expected dimension -> -1 mark each
  Everything else is full credit (max_marks minus the above deductions,
  plus existing IS/BIS compliance deductions).
"""

import os
import json
import base64
import re
from pathlib import Path
from typing import Optional, List

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

def extract_json_block(text: str) -> Optional[str]:
    """
    Robustly pulls a JSON object out of an LLM/VLM response - strips
    markdown code fences and brace-matches from the first '{' to its true
    closing '}', which is much more reliable than a naive greedy regex when
    a small local model adds preamble/fences around the JSON.
    """
    if not text:
        return None
    cleaned = re.sub(r'```(?:json)?', '', text).strip()
    start = cleaned.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == '{':
            depth += 1
        elif cleaned[i] == '}':
            depth -= 1
            if depth == 0:
                return cleaned[start:i + 1]
    return None

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
  "labeled_parts": ["list of every labeled component/part name visible in the drawing, e.g. piston, crankshaft, valve"],
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
            }],
            options={"temperature": 0.2},
        )
        text = resp["message"]["content"].strip()
        parsed_text = extract_json_block(text)
        if parsed_text:
            return json.loads(parsed_text)
    except Exception:
        pass

    return _fallback_vlm_output()

def _fallback_vlm_output() -> dict:
    return {
        "view_type": "orthographic",
        "projection_angle": "unknown",
        "views_detected": ["front", "top"],
        "dimensions": [],
        "labeled_parts": [],
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

# ── Rubric: expected parts & dimensions (from the question text) ──────────────

_DIM_PATTERN = re.compile(r'-?\d+(?:\.\d+)?\s*(?:mm|cm|m|in|inch|kg|N|kN|MPa|GPa|°|deg|rpm)\b', re.IGNORECASE)

def extract_expected_dimensions(question: str) -> List[str]:
    """Pulls dimension values (number + unit) mentioned in the question
    itself - these are the dimensions the student is expected to draw/label."""
    if not question:
        return []
    return [m.group().strip() for m in _DIM_PATTERN.finditer(question)]

def extract_expected_parts(question: str) -> List[str]:
    """
    Heuristic extraction of the components the question asks the student
    to draw/label, e.g. 'Draw a block diagram showing the boiler, turbine,
    condenser and pump' -> ['boiler', 'turbine', 'condenser', 'pump'].
    Looks for a list following cue words like showing/label/comprising/with.
    Falls back to an empty list (no part-level deduction applied) if no
    such list is found - callers can also pass an explicit list.
    """
    if not question:
        return []
    m = re.search(
        r'(?:showing|label(?:l?ing)?|comprising|consisting of|indicating|with)\s+(?:the\s+)?([^.?!]+)',
        question, re.IGNORECASE,
    )
    if not m:
        return []
    chunk = m.group(1)
    chunk = re.sub(r'\band\b', ',', chunk, flags=re.IGNORECASE)

    parts = []
    for raw in chunk.split(","):
        candidate = re.sub(r'^\s*(the|a|an)\s+', '', raw.strip(" ."), flags=re.IGNORECASE)
        if not candidate:
            continue
        if re.search(r'\d', candidate):
            # A dimension/measurement clause starts here (e.g. "marked as 50mm") -
            # everything from this point on belongs to the dimension clause, not the part list.
            break
        if len(candidate.split()) <= 4:
            parts.append(candidate)
    return parts

def _parse_dim(token: str):
    m = re.match(r'(-?\d+(?:\.\d+)?)\s*([a-zA-Z°]*)', token.strip())
    if not m:
        return None
    return float(m.group(1)), m.group(2).lower()

def score_against_rubric(vlm_output: dict, expected_parts: List[str],
                          expected_dimensions: List[str], max_marks: float) -> dict:
    """
    Applies the deduction rubric:
      - each expected dimension not detected at all       -> -0.5
      - each expected dimension detected but wrong value  -> -1
      - each expected part/component not detected          -> -1
    Starts from max_marks (full credit) and subtracts.
    """
    detected_dims = vlm_output.get("dimensions", []) or []
    detected_parts = vlm_output.get("labeled_parts", []) or []

    # Match dimensions: pair each expected dimension to the closest unmatched
    # detected one (same/compatible unit); absent -> missing, mismatched value -> wrong.
    detected_parsed = [(_parse_dim(d), d) for d in detected_dims]
    used = set()
    missing_dims, wrong_dims, matched_dims = [], [], []

    for exp_str in expected_dimensions:
        exp = _parse_dim(exp_str)
        if not exp:
            continue
        candidate_idx = None
        for idx, (det, _raw) in enumerate(detected_parsed):
            if idx in used or det is None:
                continue
            if det[1] == exp[1] or not det[1] or not exp[1]:
                candidate_idx = idx
                break
        if candidate_idx is None:
            missing_dims.append(exp_str)
            continue
        used.add(candidate_idx)
        det_val, _ = detected_parsed[candidate_idx][0]
        exp_val, _ = exp
        tol = max(0.01 * abs(exp_val), 0.5)
        if abs(det_val - exp_val) <= tol:
            matched_dims.append(exp_str)
        else:
            wrong_dims.append({"expected": exp_str, "found": detected_parsed[candidate_idx][1]})

    # Match parts (substring/case-insensitive match against detected labels)
    detected_parts_lower = [p.lower() for p in detected_parts]
    missing_parts, matched_parts = [], []
    for part in expected_parts:
        if any(part.lower() in dp or dp in part.lower() for dp in detected_parts_lower):
            matched_parts.append(part)
        else:
            missing_parts.append(part)

    dim_missing_deduction = 0.5 * len(missing_dims)
    dim_wrong_deduction = 1.0 * len(wrong_dims)
    part_missing_deduction = 1.0 * len(missing_parts)
    total_deduction = dim_missing_deduction + dim_wrong_deduction + part_missing_deduction

    return {
        "matched_parts": matched_parts,
        "missing_parts": missing_parts,
        "matched_dimensions": matched_dims,
        "missing_dimensions": missing_dims,
        "wrong_dimensions": wrong_dims,
        "dim_missing_deduction": round(dim_missing_deduction, 1),
        "dim_wrong_deduction": round(dim_wrong_deduction, 1),
        "part_missing_deduction": round(part_missing_deduction, 1),
        "total_rubric_deduction": round(total_deduction, 1),
    }

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

def evaluate_drawing(
    image_path: Optional[str] = None,
    max_marks: int = 20,
    question: str = "",
    expected_parts: Optional[List[str]] = None,
    expected_dimensions: Optional[List[str]] = None,
) -> dict:
    """
    Full drawing evaluation pipeline.

    `expected_parts` / `expected_dimensions` define the rubric: if not
    passed explicitly (e.g. from a faculty rubric), they're heuristically
    extracted from `question` text. Scoring starts from max_marks (full
    credit) and applies:
      -0.5 per expected dimension not found on the drawing
      -1   per expected dimension found with the wrong value
      -1   per expected part/component not found on the drawing
    plus any existing IS/BIS compliance deductions.

    Returns complete evaluation result dict.
    """
    # Step 1: Preprocess
    preprocessed = None
    if image_path and Path(image_path).exists():
        preprocessed = preprocess_image(image_path)

    # Step 2: YOLOv8 detection (diagnostic only - view/element presence)
    detected = detect_elements(image_path or "")

    # Step 3: VLM interpretation (this is where dimensions/parts come from)
    vlm_output = vlm_interpret(image_path or "") if image_path else _fallback_vlm_output()

    # Step 4: IS/BIS compliance
    violations = check_compliance(vlm_output, detected)
    violation_deductions = sum(v["deduction"] for v in violations)

    # Step 5: Rubric scoring (markings/dimensions/parts) - this is the
    # primary score driver per the marking rubric above.
    exp_parts = expected_parts if expected_parts is not None else extract_expected_parts(question)
    exp_dims = expected_dimensions if expected_dimensions is not None else extract_expected_dimensions(question)
    rubric = score_against_rubric(vlm_output, exp_parts, exp_dims, max_marks)

    # Step 6: Diagnostic element scoring (front/top/side/title block) - kept
    # for visibility but does not double-count against the rubric deductions.
    scored_elements = score_elements(detected)

    total_deductions = round(rubric["total_rubric_deduction"] + violation_deductions, 1)
    ai_score = max(0.0, round(max_marks - total_deductions, 1))
    ai_score = min(ai_score, max_marks)

    confidence = 0.75 if image_path else 0.5

    return {
        "ai_score": ai_score,
        "max_score": max_marks,
        "confidence": confidence,
        "rubric": rubric,
        "expected_parts": exp_parts,
        "expected_dimensions": exp_dims,
        "detected_elements": scored_elements,
        "violations": violations,
        "violation_deductions": violation_deductions,
        "total_deductions": total_deductions,
        "vlm_output": vlm_output,
        "preprocessing_applied": preprocessed is not None,
        "feedback": _generate_feedback(violations, scored_elements, rubric),
        "explanation": _generate_explanation(rubric, violations, violation_deductions, max_marks, ai_score),
    }

def _generate_explanation(rubric: dict, violations: list, violation_deductions: float,
                           max_marks: float, ai_score: float) -> str:
    lines = [f"Started from full marks ({max_marks})."]
    if rubric["matched_parts"]:
        lines.append(f"Part(s) correctly drawn/labeled: {', '.join(rubric['matched_parts'])} (no deduction).")
    if rubric["missing_parts"]:
        lines.append(
            f"Deducted {rubric['part_missing_deduction']} mark(s): missing part(s) "
            f"{', '.join(rubric['missing_parts'])} (-1 each)."
        )
    if rubric["matched_dimensions"]:
        lines.append(f"Dimension(s) correctly marked: {', '.join(rubric['matched_dimensions'])} (no deduction).")
    if rubric["missing_dimensions"]:
        lines.append(
            f"Deducted {rubric['dim_missing_deduction']} mark(s): missing dimension marking(s) "
            f"{', '.join(rubric['missing_dimensions'])} (-0.5 each)."
        )
    if rubric["wrong_dimensions"]:
        wrong_desc = ", ".join(f"expected {w['expected']}, found {w['found']}" for w in rubric["wrong_dimensions"])
        lines.append(f"Deducted {rubric['dim_wrong_deduction']} mark(s): incorrect dimension value(s) - {wrong_desc} (-1 each).")
    if violations:
        lines.append(f"Deducted {violation_deductions} mark(s) for IS/BIS compliance violations.")
    if not (rubric["missing_parts"] or rubric["missing_dimensions"] or rubric["wrong_dimensions"] or violations):
        lines.append("No deductions: all expected parts and dimensions were present and correct.")
    lines.append(f"Total: {ai_score}/{max_marks}.")
    return " ".join(lines)

def _generate_feedback(violations: list, elements: list, rubric: Optional[dict] = None) -> str:
    major = [v for v in violations if v["severity"] == "major"]
    minor = [v for v in violations if v["severity"] == "minor"]
    not_detected = [e for e in elements if e["status"] == "not_detected"]

    parts = []
    if rubric:
        if rubric["missing_parts"]:
            parts.append(
                f"Missing part(s): {', '.join(rubric['missing_parts'])} "
                f"(-{rubric['part_missing_deduction']})."
            )
        if rubric["missing_dimensions"]:
            parts.append(
                f"Missing dimension(s): {', '.join(rubric['missing_dimensions'])} "
                f"(-{rubric['dim_missing_deduction']})."
            )
        if rubric["wrong_dimensions"]:
            wrong_desc = ", ".join(f"expected {w['expected']}, found {w['found']}" for w in rubric["wrong_dimensions"])
            parts.append(f"Incorrect dimension(s): {wrong_desc} (-{rubric['dim_wrong_deduction']}).")
    if major:
        parts.append(f"{len(major)} major IS violation(s): {major[0]['issue']}.")
    if minor:
        parts.append(f"{len(minor)} minor violation(s) noted.")
    if not_detected:
        parts.append(f"Missing elements: {', '.join(e['element'] for e in not_detected)}.")
    if not parts:
        parts.append("All expected parts and dimensions detected. Drawing meets IS/BIS standards.")
    return " ".join(parts)
