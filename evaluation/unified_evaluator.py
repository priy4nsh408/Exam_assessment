"""
Unified answer evaluation engine with OCR support.

Replaces the separate theory_evaluator, numerical_grader, and
drawing_evaluator with a single entry point that:

1. Accepts an uploaded answer-paper image OR typed text
2. Runs OCR (LLaVA vision model via Ollama) to extract student text
3. Auto-detects question type if not specified
4. Scores using keyword coverage + semantic similarity
5. For numerical: checks formula presence (-1 if missing) and final answer
6. For drawing: runs VLM interpretation + IS/BIS compliance
7. Universal rule: if the question requires a mathematical equation and
   the student didn't write one, deduct 1 mark
"""

import os
import re
import json
import base64
from typing import Optional, List
from pathlib import Path

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")

# ── Stopwords for keyword extraction ─────────────────────────────────────────

STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "your", "with", "this",
    "that", "from", "have", "has", "had", "was", "were", "will", "would",
    "could", "should", "can", "their", "they", "them", "then", "than",
    "what", "when", "where", "which", "while", "about", "into", "such",
    "these", "those", "also", "each", "other", "some", "more", "most",
    "between", "being", "after", "before", "during", "over", "under",
    "above", "below", "because", "explain", "describe", "discuss",
    "define", "state", "derive", "calculate", "given", "using", "used",
    "use", "following", "based", "respect", "various", "different",
    "example", "examples", "question", "answer", "system", "value",
    "values", "case", "type", "types", "called", "known", "general",
}

# ── OCR via LLaVA Vision Model ───────────────────────────────────────────────

def preprocess_image(image_path: str) -> Optional[str]:
    """OpenCV preprocessing: grayscale → CLAHE → adaptive threshold → denoise.
    Saves preprocessed image and returns its path."""
    if not CV2_AVAILABLE or not image_path or not Path(image_path).exists():
        return None
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        edges = cv2.Canny(enhanced, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
        if lines is not None:
            angles = [line[0][1] for line in lines[:10]]
            median_angle = np.median(angles) - np.pi / 2
            if abs(median_angle) < 0.1:
                h, w = enhanced.shape
                M = cv2.getRotationMatrix2D((w // 2, h // 2), np.degrees(median_angle), 1.0)
                enhanced = cv2.warpAffine(enhanced, M, (w, h), flags=cv2.INTER_CUBIC,
                                          borderMode=cv2.BORDER_REPLICATE)

        thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        preprocessed_path = image_path.rsplit(".", 1)[0] + "_preprocessed.png"
        cv2.imwrite(preprocessed_path, cleaned)
        return preprocessed_path
    except Exception:
        return None


def image_to_base64(image_path: str) -> Optional[str]:
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def ocr_with_vlm(image_path: str, fast_mode: bool = False) -> dict:
    """Extract text from a student answer paper using LLaVA via Ollama.
    Returns {text, equations, has_diagram, method}.
    fast_mode=True uses a simpler prompt for batch/multi-page OCR."""
    if not OLLAMA_AVAILABLE:
        return {"text": "", "equations": [], "has_diagram": False, "method": "none"}

    img_b64 = image_to_base64(image_path)
    if not img_b64:
        return {"text": "", "equations": [], "has_diagram": False, "method": "none"}

    if fast_mode:
        prompt = "Read all handwritten and printed text from this image. Include mathematical equations. Output ONLY the extracted text, nothing else."
    else:
        prompt = """You are an OCR system reading a student's handwritten/printed answer paper.

Extract ALL text from this image. Include:
1. All written text exactly as it appears
2. All mathematical equations and formulas (write them in plain text, e.g. F = ma, η = 1 - T2/T1)
3. Note if there are any diagrams or drawings

Respond ONLY in this JSON format:
{
  "extracted_text": "the full text content of the answer",
  "equations": ["list of mathematical equations found"],
  "has_diagram": true/false,
  "diagram_description": "brief description of any diagram if present, or null"
}

Output ONLY valid JSON. No explanation or markdown."""

    try:
        resp = ollama.chat(
            model=OLLAMA_VISION_MODEL,
            messages=[{"role": "user", "content": prompt, "images": [img_b64]}],
            options={"temperature": 0.1, "num_predict": 1024},
        )
        text = resp["message"]["content"].strip()

        if fast_mode:
            return {
                "text": text,
                "equations": [],
                "has_diagram": False,
                "method": "llava",
            }

        parsed = _parse_json(text)
        if parsed:
            return {
                "text": parsed.get("extracted_text", ""),
                "equations": parsed.get("equations", []),
                "has_diagram": parsed.get("has_diagram", False),
                "diagram_description": parsed.get("diagram_description"),
                "method": "llava",
            }
        return {"text": text, "equations": [], "has_diagram": False, "method": "llava"}
    except Exception:
        pass

    return {"text": "", "equations": [], "has_diagram": False, "method": "none"}


# ── Drawing-specific VLM interpretation ──────────────────────────────────────

IS_RULES = [
    {
        "id": "IS696-6.3", "clause": "IS 696:1972 Clause 6.3",
        "description": "First angle projection must be used in Indian engineering drawings",
        "check_key": "projection_angle", "invalid_values": ["third_angle", "third angle"],
        "severity": "major", "deduction": 4,
    },
    {
        "id": "IS696-5.1", "clause": "IS 696:1972 Clause 5.1",
        "description": "All three principal views (front, top, side) must be present",
        "check_key": "views_detected", "min_count": 2,
        "severity": "major", "deduction": 5,
    },
    {
        "id": "IS919-4.1", "clause": "IS 919:1993 Clause 4.1",
        "description": "Dimensional tolerance notation must follow standard form",
        "check_key": "tolerances", "pattern_check": True,
        "severity": "minor", "deduction": 1,
    },
    {
        "id": "SP46-8.2", "clause": "SP:46:2003 Section 8.2",
        "description": "Title block must include drawing number, scale, and date",
        "check_key": "title_block", "required_fields": ["drawing_no", "scale", "date"],
        "severity": "minor", "deduction": 1,
    },
    {
        "id": "IS3073-3.1", "clause": "IS 3073:1967 Clause 3.1",
        "description": "Surface finish symbols must follow IS 3073 notation",
        "check_key": "surface_finish", "severity": "minor", "deduction": 1,
    },
]


def vlm_interpret_drawing(image_path: str) -> dict:
    """Uses LLaVA to interpret an engineering drawing and return structured JSON."""
    if not OLLAMA_AVAILABLE:
        return _fallback_drawing_vlm()

    img_b64 = image_to_base64(image_path)
    if not img_b64:
        return _fallback_drawing_vlm()

    prompt = """Analyze this engineering drawing and return ONLY a JSON object:
{
  "view_type": "orthographic" or "isometric" or "perspective",
  "projection_angle": "first_angle" or "third_angle" or "unknown",
  "views_detected": ["front", "top", "side"],
  "dimensions": ["45mm", "30mm"],
  "labeled_parts": ["shaft", "bearing"],
  "tolerances": ["50±0.5"],
  "GDT_symbols": ["perpendicularity"],
  "surface_finish": ["Ra 3.2"],
  "title_block": {"drawing_no": null, "scale": "1:1", "material": null, "date": null}
}
Return ONLY valid JSON."""

    try:
        resp = ollama.chat(
            model=OLLAMA_VISION_MODEL,
            messages=[{"role": "user", "content": prompt, "images": [img_b64]}],
            options={"temperature": 0.2},
        )
        parsed = _parse_json(resp["message"]["content"].strip())
        if parsed:
            return parsed
    except Exception:
        pass
    return _fallback_drawing_vlm()


def _fallback_drawing_vlm() -> dict:
    return {
        "view_type": "orthographic", "projection_angle": "unknown",
        "views_detected": ["front", "top"], "dimensions": [], "labeled_parts": [],
        "tolerances": [], "GDT_symbols": [], "surface_finish": [],
        "title_block": {"drawing_no": None, "scale": None, "material": None, "date": None},
    }


def check_compliance(vlm_output: dict) -> list:
    violations = []
    for rule in IS_RULES:
        key = rule["check_key"]
        if key == "projection_angle":
            angle = vlm_output.get("projection_angle", "").lower()
            if angle in rule.get("invalid_values", []):
                violations.append({"rule_id": rule["id"], "clause": rule["clause"],
                                   "issue": rule["description"], "severity": rule["severity"],
                                   "deduction": rule["deduction"], "found": angle})
        elif key == "views_detected":
            views = vlm_output.get("views_detected", [])
            if len(views) < rule.get("min_count", 2):
                violations.append({"rule_id": rule["id"], "clause": rule["clause"],
                                   "issue": f"Only {len(views)} view(s) detected — minimum {rule['min_count']} required",
                                   "severity": rule["severity"], "deduction": rule["deduction"], "found": views})
        elif key == "tolerances" and rule.get("pattern_check"):
            for t in vlm_output.get("tolerances", []):
                if re.search(r'[±]\s*\.\d', t):
                    violations.append({"rule_id": rule["id"], "clause": rule["clause"],
                                       "issue": f"Non-standard tolerance notation: '{t}'",
                                       "severity": rule["severity"], "deduction": rule["deduction"], "found": t})
                    break
        elif key == "title_block":
            tb = vlm_output.get("title_block", {})
            missing = [f for f in rule.get("required_fields", []) if not tb.get(f)]
            if missing:
                violations.append({"rule_id": rule["id"], "clause": rule["clause"],
                                   "issue": f"Title block missing: {', '.join(missing)}",
                                   "severity": rule["severity"], "deduction": rule["deduction"], "found": tb})
    return violations


# ── Keyword & Semantic Scoring ───────────────────────────────────────────────

def extract_keywords(text: str, top_n: int = 15) -> list:
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", text)
    freq = {}
    for tok in tokens:
        lt = tok.lower().strip("-'")
        if len(lt) < 4 or lt in STOPWORDS:
            continue
        freq[lt] = freq.get(lt, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    return [word for word, _ in ranked[:top_n]]


def keyword_coverage(student_text: str, reference_text: str, top_n: int = 15) -> dict:
    keywords = extract_keywords(reference_text, top_n=top_n)
    student_lower = student_text.lower()
    found = [k for k in keywords if k in student_lower]
    missing = [k for k in keywords if k not in found]
    return {
        "keywords_considered": keywords, "found": found, "missing": missing,
        "matched_count": len(found), "total_count": len(keywords),
        "coverage_ratio": len(found) / max(len(keywords), 1),
    }


_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None and EMBEDDINGS_AVAILABLE:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def cosine_sim(a, b) -> float:
    if not EMBEDDINGS_AVAILABLE:
        return 0.5
    import numpy as np
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def semantic_similarity(student_text: str, reference_text: str) -> float:
    if not reference_text or not student_text:
        return 0.5
    if not EMBEDDINGS_AVAILABLE:
        return 0.5
    model = get_embedding_model()
    if not model:
        return 0.5
    embeddings = model.encode([reference_text, student_text])
    return cosine_sim(embeddings[0], embeddings[1])


def batch_semantic_similarity(student_text: str, reference_texts: List[str]) -> List[float]:
    if not EMBEDDINGS_AVAILABLE or not student_text:
        return [0.5] * len(reference_texts)
    model = get_embedding_model()
    if not model:
        return [0.5] * len(reference_texts)
    all_texts = [student_text] + reference_texts
    embeddings = model.encode(all_texts)
    student_emb = embeddings[0]
    return [cosine_sim(student_emb, embeddings[i + 1]) for i in range(len(reference_texts))]


# ── Equation / Formula Detection ─────────────────────────────────────────────

_EQ_PATTERN = re.compile(r'[A-Za-zΔδηρσμπ%]{1,8}(?:\s*\([^)]*\))?\s*=\s*[^=\n.;]{2,60}')
_NUM_PATTERN = re.compile(r'-?\d+(?:\.\d+)?(?:\s*[eE][-+]?\d+)?\s*[a-zA-Z°%/]{0,6}')


def extract_equations(text: str) -> list:
    if not text:
        return []
    return [m.group().strip() for m in _EQ_PATTERN.finditer(text)]


def extract_final_number(text: str) -> Optional[str]:
    if not text:
        return None
    matches = _NUM_PATTERN.findall(text)
    return matches[-1].strip() if matches else None


def _parse_number(token: str):
    m = re.match(r'(-?\d+(?:\.\d+)?)\s*([a-zA-Z°%/]*)', token.strip())
    if not m:
        return None
    return float(m.group(1)), m.group(2).lower()


def question_requires_equation(question: str) -> bool:
    """Detect if the question asks the student to use/derive/write a mathematical equation."""
    if not question:
        return False
    eq_cues = [
        r'\bderive\b', r'\bformula\b', r'\bequation\b', r'\bcalculate\b',
        r'\bcompute\b', r'\bsolve\b', r'\bnumerical\b', r'\bfind the value\b',
        r'\bdetermine\b', r'\busing .{0,30}equation\b', r'\bapply .{0,30}formula\b',
        r'\bprove\b', r'\bshow that\b', r'\bexpression\b',
    ]
    return any(re.search(pat, question, re.IGNORECASE) for pat in eq_cues)


def equation_present_in_answer(student_text: str, reference_text: str = "",
                                expected_formula: str = "") -> bool:
    """Check if the student wrote at least one equation."""
    student_eqs = extract_equations(student_text)
    if not student_eqs:
        return False
    if not expected_formula and not reference_text:
        return True
    ref_eq_source = expected_formula or " ".join(extract_equations(reference_text))
    if not ref_eq_source:
        return True
    ref_tokens = {t.lower() for t in re.findall(r'[A-Za-zΔδηρσμπ]{1,8}', ref_eq_source) if len(t) <= 8}
    student_tokens = {t.lower() for t in re.findall(r'[A-Za-zΔδηρσμπ]{1,8}', " ".join(student_eqs))}
    return len(ref_tokens & student_tokens) > 0


def final_answer_correct(student_text: str, reference_text: str,
                          expected_final: str = "", tolerance: float = 0.02) -> bool:
    expected = expected_final or extract_final_number(reference_text)
    if not expected:
        return True
    exp = _parse_number(expected)
    got = _parse_number(extract_final_number(student_text) or "")
    if not exp or not got:
        return False
    if exp[0] == 0:
        return abs(got[0]) < 1e-6
    return abs(got[0] - exp[0]) / abs(exp[0]) <= tolerance


# ── Question Type Auto-Detection ─────────────────────────────────────────────

def detect_question_type(question: str, has_diagram: bool = False) -> str:
    q = question.lower()
    if has_diagram:
        return "drawing"
    drawing_cues = ["draw", "sketch", "diagram", "engineering drawing", "orthographic",
                    "isometric", "projection", "front view", "top view", "side view"]
    if any(cue in q for cue in drawing_cues):
        return "drawing"
    numerical_cues = ["calculate", "compute", "find the value", "determine the",
                      "solve", "numerical", "how much", "how many", "what is the value"]
    if any(cue in q for cue in numerical_cues):
        return "numerical"
    return "theory"


# ── LLM Step Grading for Numerical ───────────────────────────────────────────

def _llm_grade_steps(question: str, student_solution: str, reference_answer: str,
                     subject: str, max_marks: int) -> Optional[dict]:
    if not OLLAMA_AVAILABLE:
        return None

    prompt = f"""You are an expert {subject} professor grading a numerical solution.

QUESTION: {question}

{"REFERENCE SOLUTION:" + chr(10) + reference_answer if reference_answer else ""}

STUDENT SOLUTION:
{student_solution}

Evaluate each step EXCLUDING formula check and final answer check (handled separately).
Focus on: substitution of values, unit handling, arithmetic, boundary conditions.

Respond ONLY in JSON:
{{
  "steps": [
    {{
      "step": 1, "description": "What this step calculates",
      "student_work": "What student wrote", "expected": "Correct value",
      "correct": true/false,
      "error_type": "correct" or "substitution_error" or "unit_error" or "arithmetic_error" or "boundary_condition_error",
      "marks": <max for step>, "earned": <earned>,
      "explanation": "Brief explanation"
    }}
  ],
  "total_earned": <sum>, "total_marks": <sum>,
  "feedback": "1-2 sentences on working quality",
  "confidence": <0.0-1.0>
}}
Output ONLY raw JSON."""

    try:
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2, "num_predict": 512},
        )
        result = _parse_json(resp["message"]["content"].strip())
        if result:
            total_m = result.get("total_marks", max_marks) or max_marks
            total_e = result.get("total_earned", 0)
            result["ai_score"] = round((total_e / total_m) * max_marks, 1)
            return result
    except Exception:
        pass
    return None


def _heuristic_grade_steps(student_solution: str, max_marks: int) -> dict:
    lines = [l.strip() for l in student_solution.split("\n") if l.strip()]
    step_count = max(len(lines), 3)
    marks_per_step = round(max_marks / step_count, 1)
    steps = []
    earned_total = 0
    for i, line in enumerate(lines[:step_count]):
        has_calc = bool(re.search(r'=\s*[\d\.\-]', line))
        earned = marks_per_step if has_calc else marks_per_step * 0.5
        earned_total += earned
        steps.append({
            "step": i + 1, "description": f"Step {i+1}",
            "student_work": line, "expected": "See reference",
            "correct": has_calc, "error_type": "correct" if has_calc else "arithmetic_error",
            "marks": marks_per_step, "earned": round(earned, 1),
            "explanation": "Heuristic evaluation — LLM not available",
        })
    return {
        "steps": steps, "total_earned": round(earned_total, 1), "total_marks": max_marks,
        "ai_score": round(min(earned_total, max_marks), 1),
        "feedback": "Heuristic evaluation — connect Ollama for full step-level grading.",
        "confidence": 0.4,
    }


# ── LLM Feedback (optional, never affects score) ────────────────────────────

def _llm_feedback(question: str, reference: str, student_text: str,
                  kw: dict, similarity: float, subject: str) -> str:
    if not OLLAMA_AVAILABLE:
        return ""
    prompt = f"""You are an expert {subject or 'engineering'} professor.
A student's answer was auto-graded against the source material.

QUESTION: {question}
REFERENCE: {reference}
STUDENT ANSWER: {student_text}

Matched keywords: {', '.join(kw['found']) or 'none'}
Missing keywords: {', '.join(kw['missing']) or 'none'}
Semantic similarity: {similarity:.0%}

Write 2-3 sentences of specific, constructive feedback. No JSON."""

    try:
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3, "num_predict": 256},
        )
        return resp["message"]["content"].strip()
    except Exception:
        return ""


# ── Drawing rubric helpers ───────────────────────────────────────────────────

_DIM_PATTERN = re.compile(r'-?\d+(?:\.\d+)?\s*(?:mm|cm|m|in|inch|kg|N|kN|MPa|GPa|°|deg|rpm)\b', re.IGNORECASE)

def extract_expected_dimensions(question: str) -> List[str]:
    if not question:
        return []
    return [m.group().strip() for m in _DIM_PATTERN.finditer(question)]

def extract_expected_parts(question: str) -> List[str]:
    if not question:
        return []
    m = re.search(
        r'(?:showing|label(?:l?ing)?|comprising|consisting of|indicating|with)\s+(?:the\s+)?([^.?!]+)',
        question, re.IGNORECASE,
    )
    if not m:
        return []
    chunk = re.sub(r'\band\b', ',', m.group(1), flags=re.IGNORECASE)
    parts = []
    for raw in chunk.split(","):
        candidate = re.sub(r'^\s*(the|a|an)\s+', '', raw.strip(" ."), flags=re.IGNORECASE)
        if not candidate or re.search(r'\d', candidate):
            break
        if len(candidate.split()) <= 4:
            parts.append(candidate)
    return parts


def _parse_dim(token: str):
    m = re.match(r'(-?\d+(?:\.\d+)?)\s*([a-zA-Z°]*)', token.strip())
    if not m:
        return None
    return float(m.group(1)), m.group(2).lower()


# ── JSON Parsing ─────────────────────────────────────────────────────────────

def _extract_json_block(text: str) -> Optional[str]:
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


def _parse_json(text: str) -> Optional[dict]:
    block = _extract_json_block(text)
    if not block:
        return None
    try:
        return json.loads(block)
    except Exception:
        return None


# ── LLM-Based Comprehensive Grading ─────────────────────────────────────────

def _llm_grade_answer(question: str, student_answer: str, reference_answer: str,
                      max_marks: int, subject: str, question_type: str,
                      expected_formula: str = "", expected_final_answer: str = "") -> Optional[dict]:
    """Use LLM to read both the answer scheme and student answer, then grade
    based on evaluation metrics: keyword coverage, conceptual accuracy,
    equation/formula presence, step correctness, and completeness."""
    if not OLLAMA_AVAILABLE or not student_answer.strip():
        return None

    formula_section = ""
    if expected_formula:
        formula_section = f"\nEXPECTED FORMULA: {expected_formula}"
    if expected_final_answer:
        formula_section += f"\nEXPECTED FINAL ANSWER: {expected_final_answer}"

    prompt = f"""You are an expert {subject or 'engineering'} professor grading a student's answer.

QUESTION ({question_type}, {max_marks} marks):
{question}

ANSWER SCHEME / MODEL ANSWER:
{reference_answer[:3000]}
{formula_section}

STUDENT'S ANSWER:
{student_answer[:3000]}

Grade the student's answer against the answer scheme. Evaluate on these metrics:

1. **Keyword Coverage** (how many key technical terms from the scheme appear in the student answer)
2. **Conceptual Accuracy** (does the student demonstrate correct understanding)
3. **Completeness** (are all required points/steps covered)
4. **Mathematical Equations** (if required: did the student write the correct formula/equation)
5. **Final Answer** (for numerical: is the final value correct)
6. **Clarity & Structure** (is the answer well-organized)

SCORING RULES:
- Maximum marks: {max_marks}
- If a mathematical equation is required but missing: deduct 1 mark
- For numerical: if formula not mentioned, deduct 1 mark; if final answer wrong, deduct 2 marks
- Award partial marks for partially correct answers

Respond ONLY in this JSON format:
{{
  "score": <number between 0 and {max_marks}>,
  "keyword_analysis": {{
    "found": ["list of key terms student mentioned"],
    "missing": ["list of key terms student missed"],
    "coverage_percent": <0-100>
  }},
  "conceptual_accuracy": <0-100>,
  "completeness": <0-100>,
  "equation_present": true/false,
  "formula_correct": true/false,
  "final_answer_correct": true/false,
  "deductions": [
    {{"reason": "why marks deducted", "marks": <number>}}
  ],
  "feedback": "2-3 sentences of specific feedback explaining the score",
  "explanation": "Detailed breakdown of how marks were awarded and deducted",
  "confidence": <0.0 to 1.0>
}}
Output ONLY valid JSON. No markdown or explanation outside the JSON."""

    try:
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2, "num_predict": 512},
        )
        parsed = _parse_json(resp["message"]["content"].strip())
        if parsed and "score" in parsed:
            score = max(0.0, min(float(parsed["score"]), max_marks))
            kw_analysis = parsed.get("keyword_analysis", {})
            return {
                "ai_score": round(score, 1),
                "max_score": max_marks,
                "confidence": min(0.95, max(0.3, float(parsed.get("confidence", 0.7)))),
                "feedback": parsed.get("feedback", ""),
                "explanation": parsed.get("explanation", ""),
                "keywords": {
                    "found": kw_analysis.get("found", []),
                    "missing": kw_analysis.get("missing", []),
                    "matched_count": len(kw_analysis.get("found", [])),
                    "total_count": len(kw_analysis.get("found", [])) + len(kw_analysis.get("missing", [])),
                    "coverage_ratio": (kw_analysis.get("coverage_percent", 50) or 50) / 100,
                },
                "conceptual_accuracy": parsed.get("conceptual_accuracy", 0),
                "completeness": parsed.get("completeness", 0),
                "formula_mentioned": parsed.get("formula_correct", True),
                "final_answer_correct": parsed.get("final_answer_correct", True),
                "equation_present": parsed.get("equation_present", True),
                "deductions": parsed.get("deductions", []),
                "llm_graded": True,
            }
    except Exception:
        pass
    return None


def _detect_question_numbers_on_page(image_path: str) -> List[int]:
    """Crop the left ~15% of a page and run Tesseract to detect question numbers."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return []
    try:
        img = Image.open(image_path)
        w, h = img.size
        left_strip = img.crop((0, 0, int(w * 0.18), h))
        text = pytesseract.image_to_string(left_strip, config="--psm 6")
        numbers = []
        for m in re.finditer(r'(?:^|[Qq\s])(\d{1,2})\b', text):
            n = int(m.group(1))
            if 1 <= n <= 30:
                numbers.append(n)
        return sorted(set(numbers))
    except Exception:
        return []


def _detect_question_number_vlm(image_path: str) -> List[int]:
    """Fallback question-number detector using the vision model itself.

    Tesseract only recognizes printed text reliably - on handwritten margin
    numbers it frequently finds nothing at all. LLaVA is already looking at
    every page for grading and is much better at reading handwriting, so
    it's a natural fallback for the pages that defeat Tesseract, rather than
    giving up and falling back to a blind page-count guess."""
    if not OLLAMA_AVAILABLE:
        print("[page-detect-vlm] ollama package not importable - skipping VLM fallback")
        return []
    img_b64 = image_to_base64(image_path)
    if not img_b64:
        print(f"[page-detect-vlm] could not read image: {image_path}")
        return []
    prompt = ("Look only at the top of this page and its left margin. Is there a "
              "question number written there (e.g. 'Q1', 'Q.2', '3)', '5', 'Q5 a)')? "
              "Reply with ONLY the number by itself (e.g. '3'), or the single word "
              "'none' if no question number is visible anywhere on the page. No other text.")
    try:
        resp = ollama.chat(
            model=OLLAMA_VISION_MODEL,
            messages=[{"role": "user", "content": prompt, "images": [img_b64]}],
            options={"temperature": 0.1, "num_predict": 20},
        )
        text = resp["message"]["content"].strip()
        print(f"[page-detect-vlm] {Path(image_path).name}: raw reply = {text!r}")
        numbers = []
        for m in re.finditer(r'(?:^|[Qq.\s])(\d{1,2})\b', text):
            n = int(m.group(1))
            if 1 <= n <= 30:
                numbers.append(n)
        return sorted(set(numbers))
    except Exception as e:
        print(f"[page-detect-vlm] error on {Path(image_path).name}: {e}")
        return []


def _classify_page_by_similarity(image_path: str, questions: List[dict]) -> Optional[int]:
    """Last-resort page classifier for pages with no legible question number
    at all - the common case for continuation pages of a multi-page answer,
    which students very rarely renumber.

    An earlier version of this asked the vision model to read the page AND
    pick from a numbered list of questions in a single prompt. Testing
    against a real scanned script showed that fails badly: it defaulted to
    guessing question 1 on pages with completely unrelated content (a page
    unmistakably about widespread fatigue damage - Q4 - was misclassified
    as Q1), while other clearly-attributable pages came back "none". A
    small local vision model isn't reliable at that compound a judgment
    call in one shot.

    This splits the task instead: OCR the page with `ocr_with_vlm` (the
    same call already proven reliable for transcribing typed single-image
    submissions elsewhere in this module), then match the extracted text to
    the closest question by sentence-embedding cosine similarity - the same
    technique the theory evaluator already relies on for scoring, not a
    vision-model judgment call at all.

    Returns the 1-based position of the best-matching question in
    `questions` (matching q_to_pages' positional keys), or None if OCR
    produced nothing usable."""
    if not questions:
        return None
    if not EMBEDDINGS_AVAILABLE:
        # batch_semantic_similarity degrades to an identical constant score
        # for every candidate when the embedding model isn't installed -
        # picking a "best" match out of a tie would silently always return
        # position 1, reproducing the exact "everything defaults to Q1" bug
        # this function exists to fix, just from a different cause.
        print("[page-classify-sim] sentence-transformers not available - skipping similarity match")
        return None
    ocr_result = ocr_with_vlm(image_path, fast_mode=True)
    page_text = (ocr_result or {}).get("text", "").strip()
    if not page_text or len(page_text) < 15:
        print(f"[page-classify-sim] {Path(image_path).name}: OCR produced no usable text")
        return None

    reference_texts = [
        f"{q.get('question_text', '')} {q.get('reference_answer', '')}".strip()
        for q in questions
    ]
    scores = batch_semantic_similarity(page_text, reference_texts)
    if not scores:
        return None
    best_pos = max(range(len(scores)), key=lambda i: scores[i])
    best_score = scores[best_pos]
    best_label = questions[best_pos].get("question_number", best_pos + 1)
    print(f"[page-classify-sim] {Path(image_path).name}: best match Q{best_label} (score {best_score:.2f})")
    if best_score < 0.15:
        print(f"[page-classify-sim] {Path(image_path).name}: below confidence threshold, inconclusive")
        return None
    return best_pos + 1


def _ocr_half_page(image_path: str, half: str) -> str:
    """OCR just the top or bottom ~58% of a page (slight overlap so a
    sentence straddling the middle isn't cleanly severed), saved to a temp
    file since ocr_with_vlm takes a path. Used to detect and split
    boundary pages that mix the tail of one answer with the start of the
    next - confirmed to happen in practice (a page ending one derivation
    and starting the next question's on the same sheet)."""
    try:
        from PIL import Image
    except ImportError:
        return ""
    try:
        img = Image.open(image_path)
        w, h = img.size
        if half == "top":
            crop = img.crop((0, 0, w, int(h * 0.58)))
        else:
            crop = img.crop((0, int(h * 0.42), w, h))
        tmp_path = image_path.rsplit(".", 1)[0] + f"_{half}half.png"
        crop.save(tmp_path)
        result = ocr_with_vlm(tmp_path, fast_mode=True)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return (result or {}).get("text", "").strip()
    except Exception:
        return ""


def _split_boundary_page(image_path: str, questions: List[dict], whole_page_match: int) -> Optional[dict]:
    """Check whether a page classified via _classify_page_by_similarity is
    actually a boundary page mixing two answers, by classifying its top and
    bottom halves separately. Returns {question_position: fragment_text}
    for both halves if they disagree (each above the confidence threshold),
    or None if the page is a normal single-question page.
    """
    if not EMBEDDINGS_AVAILABLE or len(questions) < 2:
        return None
    top_text = _ocr_half_page(image_path, "top")
    bottom_text = _ocr_half_page(image_path, "bottom")
    if not top_text or not bottom_text:
        return None

    reference_texts = [
        f"{q.get('question_text', '')} {q.get('reference_answer', '')}".strip()
        for q in questions
    ]
    top_scores = batch_semantic_similarity(top_text, reference_texts)
    bottom_scores = batch_semantic_similarity(bottom_text, reference_texts)
    if not top_scores or not bottom_scores:
        return None

    top_pos = max(range(len(top_scores)), key=lambda i: top_scores[i])
    bottom_pos = max(range(len(bottom_scores)), key=lambda i: bottom_scores[i])
    if (top_pos == bottom_pos or top_scores[top_pos] < 0.15
            or bottom_scores[bottom_pos] < 0.15):
        return None  # not a boundary page - one question dominates the whole page

    print(f"[page-detect] {Path(image_path).name}: boundary page detected - "
          f"top half -> position {top_pos + 1}, bottom half -> position {bottom_pos + 1}")
    return {top_pos + 1: top_text, bottom_pos + 1: bottom_text}


def _map_pages_to_questions(image_paths: List[str], questions) -> tuple:
    """Build a mapping: question_number -> [page_indices], plus a
    page_fragments dict for boundary pages that mix two answers.

    `questions` accepts either an int (just the question count) or the list
    of parsed question dicts (question_number/question_text) - passing the
    list enables the content-matching and boundary-splitting fallbacks below.

    Cascade per page, cheapest first:
      1. Tesseract OCR on the left margin (fast, free; works on printed numbers)
      2. LLaVA asked to read just the numeral (works when handwriting is clear)
      3. OCR the page + match its text to a question by semantic similarity
         (works even on unnumbered continuation pages - confirmed to be the
         common case: on a real scanned script, 11 of 12 pages had no
         numeral at all, so the page classifier is doing most of the work)
      4. Check if that page is actually a boundary page mixing two answers
         (confirmed to happen in practice - a page ending one derivation and
         starting the next question on the same sheet), by classifying its
         top and bottom halves separately. If they disagree, the page
         contributes its relevant half to each question instead of being
         forced entirely into whichever one won the whole-page classification
         - which was flipping non-deterministically between runs since
         OCR sampling isn't fully deterministic right at a genuine 50/50
         content boundary.

    Returns (q_to_pages, page_fragments) where page_fragments maps
    page_index -> {question_position: fragment_text} for boundary pages only.
    """
    if isinstance(questions, int):
        total_questions = questions
        question_list: List[dict] = []
    else:
        question_list = questions or []
        total_questions = len(question_list)

    q_to_pages = {q: [] for q in range(1, total_questions + 1)}
    page_fragments: dict = {}
    page_detections = []
    for i, path in enumerate(image_paths):
        detected = _detect_question_numbers_on_page(path)
        if not detected:
            print(f"[page-detect] Page {i+1}: Tesseract found nothing, trying LLaVA numeral read...")
            vlm_detected = _detect_question_number_vlm(path)
            if vlm_detected:
                print(f"[page-detect] Page {i+1}: LLaVA read numeral {vlm_detected}")
                detected = vlm_detected
            elif question_list:
                print(f"[page-detect] Page {i+1}: no numeral found, trying OCR+similarity match...")
                matched = _classify_page_by_similarity(path, question_list)
                if matched:
                    print(f"[page-detect] Page {i+1}: similarity match -> position {matched}")
                    detected = [matched]
                    boundary = _split_boundary_page(path, question_list, matched)
                    if boundary:
                        detected = list(boundary.keys())
                        page_fragments[i] = boundary
                else:
                    print(f"[page-detect] Page {i+1}: similarity match also inconclusive")
            else:
                print(f"[page-detect] Page {i+1}: LLaVA numeral read also found nothing")
        page_detections.append(detected)
        print(f"[page-detect] Page {i+1}: found Q numbers {detected}")
        for qn in detected:
            if qn in q_to_pages:
                q_to_pages[qn].append(i)

    # For pages with no detection, assign to the last detected question (continuation)
    last_q = None
    for i, detected in enumerate(page_detections):
        if detected:
            last_q = detected[-1]
        elif last_q and last_q in q_to_pages and i not in q_to_pages[last_q]:
            q_to_pages[last_q].append(i)
            print(f"[page-detect] Page {i+1}: no Q number, assigned to Q{last_q} (continuation)")

    return q_to_pages, page_fragments


def _resolve_page_indices(page_map: Optional[dict], question_index: int,
                          total_questions: int, n_pages: int) -> List[int]:
    """Pick which page indices belong to a question: use page_map (from
    _map_pages_to_questions) when it found something, otherwise fall back
    to a page-count estimate scaled to the actual pages-to-questions ratio
    (not scanning every remaining page)."""
    q_num = question_index + 1
    if page_map and q_num in page_map and page_map[q_num]:
        indices = list(page_map[q_num])
        print(f"[grade-pages] Q{q_num}: using mapped pages {[i + 1 for i in indices]}")
        return indices

    pages_per_answer = max(1, round(n_pages / max(total_questions, 1)))
    est_start = question_index * pages_per_answer
    est_end = min(n_pages, est_start + pages_per_answer)
    indices = list(range(est_start, est_end))
    print(f"[grade-pages] Q{q_num}: no page map, assuming pages "
          f"{[i + 1 for i in indices] or 'none (out of range)'} "
          f"(~{pages_per_answer} pages/answer)")
    return indices


def _ocr_pages(image_paths: List[str], page_indices: List[int],
               question_position: Optional[int] = None,
               page_fragments: Optional[dict] = None) -> str:
    """OCR a specific set of already-identified pages and concatenate their
    text, so grading can go through the normal text-based path instead of
    asking the vision model to judge relevance and assign a score directly
    from the raw image in a single prompt - testing against a real scanned
    script showed that compound task is unreliable (LLaVA marking pages
    "not relevant" even when they were, in fact, the correct answer, which
    silently collapsed every score to a fixed 30% neutral default via
    semantic_similarity's empty-text fallback). Plain OCR transcription is
    the same call already proven reliable for the page-classification fix.

    For a boundary page (recorded in page_fragments - one that mixes the
    tail of one answer with the start of the next), uses the already-split
    half-page fragment for this specific question instead of re-OCRing the
    whole page, which would otherwise pull in the other question's content
    too."""
    texts = []
    for idx in page_indices:
        if idx < 0 or idx >= len(image_paths):
            continue
        fragment = None
        if page_fragments and idx in page_fragments and question_position is not None:
            fragment = page_fragments[idx].get(question_position)
        if fragment is not None:
            page_text = fragment.strip()
        else:
            ocr_result = ocr_with_vlm(image_paths[idx], fast_mode=True)
            page_text = (ocr_result or {}).get("text", "").strip()
        if page_text:
            texts.append(page_text)
    return "\n".join(texts)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN UNIFIED EVALUATOR
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate(
    question: str,
    student_answer: str = "",
    answer_image_path: Optional[str] = None,
    answer_image_paths: Optional[List[str]] = None,
    reference_answer: str = "",
    max_marks: int = 10,
    subject: str = "",
    question_type: str = "auto",
    expected_formula: str = "",
    expected_final_answer: str = "",
    expected_parts: Optional[List[str]] = None,
    expected_dimensions: Optional[List[str]] = None,
    keyword_weight: float = 0.4,
    semantic_weight: float = 0.6,
    skip_llm_feedback: bool = False,
    question_index: int = 0,
    total_questions: int = 1,
    page_map: Optional[dict] = None,
    page_fragments: Optional[dict] = None,
) -> dict:
    """
    Unified evaluation entry point.

    Accepts either typed student_answer text OR an answer_image_path
    (photograph of the answer paper). If an image is provided, OCR
    extracts the text first.

    Scoring:
      - Theory: keyword_weight * keyword_coverage + semantic_weight * semantic_similarity
      - Numerical: step-level grading + formula check (-1) + final answer check (-1)
      - Drawing: VLM interpretation + IS/BIS compliance + part/dimension rubric
      - Universal: if question requires an equation and student didn't write one → -1 mark

    Returns a unified result dict with all scoring details.
    """

    ocr_result = None
    preprocessed = False

    # ── Step 1: OCR if image provided ────────────────────────────────────
    if answer_image_path and Path(answer_image_path).exists():
        prep_path = preprocess_image(answer_image_path)
        preprocessed = prep_path is not None

        ocr_result = ocr_with_vlm(answer_image_path)
        if ocr_result["text"]:
            student_answer = ocr_result["text"]

    # ── Step 2: Detect question type ─────────────────────────────────────
    has_diagram = (ocr_result or {}).get("has_diagram", False)
    if question_type == "auto":
        question_type = detect_question_type(question, has_diagram)

    # ── Step 3: Grade ──────────────────────────────────────────────────
    result = None

    # Scanned/handwritten PDF: OCR the pages already identified as this
    # question's answer (via page_map or the estimated range), then let it
    # flow through the normal text-based grading path below - rather than
    # asking the vision model to judge relevance and assign a score
    # directly from the raw image, which testing showed is unreliable.
    if answer_image_paths and not student_answer.strip() and question_type != "drawing":
        page_indices = _resolve_page_indices(page_map, question_index, total_questions, len(answer_image_paths))
        combined_text = _ocr_pages(answer_image_paths, page_indices,
                                   question_position=question_index + 1, page_fragments=page_fragments)
        if combined_text:
            student_answer = combined_text
            ocr_result = {"text": combined_text, "equations": [], "has_diagram": False, "method": "vlm_pages"}

    # Text-based LLM grading (reads both documents)
    if result is None and question_type != "drawing" and student_answer.strip():
        result = _llm_grade_answer(
            question, student_answer, reference_answer, max_marks,
            subject, question_type, expected_formula, expected_final_answer,
        )

    # Fall back to type-specific heuristic scoring if LLM unavailable
    if result is None:
        if question_type == "drawing":
            result = _evaluate_drawing(
                question, answer_image_path, reference_answer, max_marks,
                expected_parts, expected_dimensions,
            )
        elif question_type == "numerical":
            result = _evaluate_numerical(
                question, student_answer, reference_answer, max_marks,
                subject, expected_formula, expected_final_answer,
            )
        else:
            result = _evaluate_theory(
                question, student_answer, reference_answer, max_marks,
                subject, keyword_weight, semantic_weight, skip_llm_feedback,
            )

    # ── Step 4: Universal equation deduction ─────────────────────────────
    # If LLM graded, it already applied deductions — use its findings.
    # Otherwise, apply heuristic equation check.
    llm_graded = result.get("llm_graded", False)

    if llm_graded:
        eq_required = question_requires_equation(question)
        eq_present = result.get("equation_present", True)
        eq_deducted = eq_required and not eq_present
    else:
        eq_required = question_requires_equation(question)
        eq_present = equation_present_in_answer(
            student_answer, reference_answer, expected_formula
        )
        eq_deducted = False

        if eq_required and not eq_present and question_type != "drawing":
            result["ai_score"] = max(0.0, round(result["ai_score"] - 1.0, 1))
            eq_deducted = True
            result["feedback"] = (result.get("feedback", "") +
                " Mathematical equation/formula was required but not found in the answer (-1 mark).")
            result["explanation"] = (result.get("explanation", "") +
                " Deducted 1 mark: the question required a mathematical equation but none was written.")

    # ── Step 5: Build unified response ───────────────────────────────────
    result.update({
        "question_type": question_type,
        "ocr_used": ocr_result is not None,
        "ocr_method": (ocr_result or {}).get("method", "none"),
        "ocr_text": (ocr_result or {}).get("text", ""),
        "preprocessed": preprocessed,
        "equation_required": eq_required,
        "equation_present": eq_present,
        "equation_deducted": eq_deducted,
    })

    return result


# ── Type-specific scoring functions ──────────────────────────────────────────

def _evaluate_theory(question: str, student_answer: str, reference_answer: str,
                     max_marks: int, subject: str,
                     kw_weight: float, sem_weight: float,
                     skip_feedback: bool) -> dict:
    reference_answer = reference_answer or ""
    kw = keyword_coverage(student_answer, reference_answer)
    similarity = semantic_similarity(student_answer, reference_answer)

    blended = kw_weight * kw["coverage_ratio"] + sem_weight * similarity
    ai_score = max(0.0, min(round(blended * max_marks, 1), max_marks))

    feedback = "" if skip_feedback else _llm_feedback(question, reference_answer, student_answer, kw, similarity, subject)
    if not feedback:
        feedback = (f"Matched {kw['matched_count']}/{kw['total_count']} key terms "
                    f"({kw['coverage_ratio']:.0%} coverage). "
                    f"Semantic similarity: {similarity:.0%}.")

    confidence = round(min(0.95, 0.5 + similarity * 0.3 + kw["coverage_ratio"] * 0.2), 2)

    kw_marks = round(kw["coverage_ratio"] * kw_weight * max_marks, 1)
    sem_marks = round(similarity * sem_weight * max_marks, 1)
    explanation = (
        f"Keyword coverage: {kw['matched_count']}/{kw['total_count']} terms matched "
        f"({kw_marks}/{round(kw_weight * max_marks, 1)} marks). "
        f"Semantic similarity: {similarity:.0%} ({sem_marks}/{round(sem_weight * max_marks, 1)} marks). "
        f"Missing terms: {', '.join(kw['missing']) or 'none'}. "
        f"Total: {ai_score}/{max_marks}."
    )

    return {
        "ai_score": ai_score, "max_score": max_marks,
        "keyword_score": round(kw["coverage_ratio"] * max_marks, 1),
        "semantic_score": round(similarity * max_marks, 1),
        "confidence": confidence, "feedback": feedback, "explanation": explanation,
        "keywords": kw, "similarity": round(similarity, 3),
    }


def _evaluate_numerical(question: str, student_solution: str, reference_answer: str,
                        max_marks: int, subject: str,
                        expected_formula: str, expected_final: str) -> dict:
    step_result = _llm_grade_steps(question, student_solution, reference_answer, subject, max_marks)
    if step_result is None:
        step_result = _heuristic_grade_steps(student_solution, max_marks)

    base_score = step_result["ai_score"]
    has_formula = equation_present_in_answer(student_solution, reference_answer, expected_formula)
    answer_ok = final_answer_correct(student_solution, reference_answer, expected_final)

    deductions = 0.0
    deduction_reasons = []
    if not has_formula:
        deductions += 1.0
        deduction_reasons.append("Formula/equation not mentioned (-1)")
    if not answer_ok:
        deductions += 2.0
        deduction_reasons.append("Final answer does not match expected value (-2)")

    ai_score = max(0.0, min(round(base_score - deductions, 1), max_marks))

    feedback = step_result.get("feedback", "")
    if deduction_reasons:
        feedback = (feedback + " " if feedback else "") + " ".join(deduction_reasons)

    lines = [f"Step-level score: {base_score}/{max_marks}."]
    if not has_formula:
        lines.append("Deducted 1 mark: expected formula not written.")
    if not answer_ok:
        lines.append("Deducted 2 marks: final answer incorrect.")
    if has_formula and answer_ok:
        lines.append("No deductions: formula present and final answer correct.")
    lines.append(f"Total: {ai_score}/{max_marks}.")

    step_result.update({
        "ai_score": ai_score, "max_score": max_marks, "base_score": base_score,
        "formula_mentioned": has_formula, "final_answer_correct": answer_ok,
        "deductions": round(deductions, 1), "feedback": feedback,
        "explanation": " ".join(lines),
        "confidence": step_result.get("confidence", 0.5),
    })
    return step_result


def _evaluate_drawing(question: str, image_path: Optional[str], reference_answer: str,
                      max_marks: int, expected_parts: Optional[List[str]],
                      expected_dimensions: Optional[List[str]]) -> dict:
    vlm_output = vlm_interpret_drawing(image_path) if image_path else _fallback_drawing_vlm()
    violations = check_compliance(vlm_output)
    violation_ded = sum(v["deduction"] for v in violations)

    exp_parts = expected_parts if expected_parts is not None else extract_expected_parts(question)
    exp_dims = expected_dimensions if expected_dimensions is not None else extract_expected_dimensions(question)

    detected_parts_lower = [p.lower() for p in (vlm_output.get("labeled_parts") or [])]
    detected_dims = vlm_output.get("dimensions") or []

    missing_parts = [p for p in exp_parts if not any(p.lower() in dp or dp in p.lower() for dp in detected_parts_lower)]
    missing_dims = [d for d in exp_dims if d not in detected_dims]

    part_ded = 1.0 * len(missing_parts)
    dim_ded = 0.5 * len(missing_dims)
    total_ded = round(part_ded + dim_ded + violation_ded, 1)
    ai_score = max(0.0, min(round(max_marks - total_ded, 1), max_marks))

    lines = [f"Started from {max_marks} marks."]
    if missing_parts:
        lines.append(f"Missing part(s): {', '.join(missing_parts)} (-{part_ded}).")
    if missing_dims:
        lines.append(f"Missing dimension(s): {', '.join(missing_dims)} (-{dim_ded}).")
    if violations:
        lines.append(f"IS/BIS violations: {violation_ded} mark(s) deducted.")
    if not (missing_parts or missing_dims or violations):
        lines.append("No deductions.")
    lines.append(f"Total: {ai_score}/{max_marks}.")

    feedback_parts = []
    if missing_parts:
        feedback_parts.append(f"Missing: {', '.join(missing_parts)}.")
    if missing_dims:
        feedback_parts.append(f"Missing dimensions: {', '.join(missing_dims)}.")
    if violations:
        feedback_parts.append(f"{len(violations)} IS/BIS violation(s).")
    if not feedback_parts:
        feedback_parts.append("All expected elements present. Drawing meets standards.")

    return {
        "ai_score": ai_score, "max_score": max_marks,
        "confidence": 0.75 if image_path else 0.5,
        "feedback": " ".join(feedback_parts), "explanation": " ".join(lines),
        "vlm_output": vlm_output, "violations": violations,
        "violation_deductions": violation_ded,
        "expected_parts": exp_parts, "expected_dimensions": exp_dims,
        "missing_parts": missing_parts, "missing_dimensions": missing_dims,
        "total_deductions": total_ded,
    }
