"""
Numerical step-level grader.

Scoring rule (as specified):
  1. Start from the step-level "working" score (LLM chain-of-thought grading
     of substitution/units/arithmetic/boundary conditions, or a heuristic
     fallback) - this is "marks for the rest" of the solution.
  2. Deduct 1 mark if the student never wrote/used the expected formula.
  3. Deduct 1 mark if the student's final numeric answer doesn't match the
     expected final answer.
  Both checks are graded against `reference_answer` - the raw-data-derived
  answer_key/source_chunk for the question - unless an explicit
  `expected_formula` / `expected_final_answer` is supplied (e.g. from a
  faculty-authored rubric, which always takes priority when given).
"""

import os
import json
import re
from typing import List, Optional

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

def extract_json_block(text: str) -> Optional[str]:
    """
    Robustly pulls a JSON object out of an LLM response. Small local models
    (e.g. Mistral 7B) frequently wrap JSON in ```json ... ``` fences or add
    a sentence of preamble/trailing commentary - brace-matching from the
    first '{' to its true closing '}' is much more reliable than a naive
    greedy regex for that case.
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

def parse_llm_json(text: str) -> Optional[dict]:
    block = extract_json_block(text)
    if not block:
        return None
    try:
        return json.loads(block)
    except Exception:
        return None

ERROR_CATEGORIES = {
    "formula_error": "Wrong formula or equation used",
    "substitution_error": "Correct formula but wrong value substituted",
    "unit_error": "Incorrect units or missing unit conversion",
    "arithmetic_error": "Correct setup but arithmetic/calculation mistake",
    "boundary_condition_error": "Wrong boundary or initial condition applied",
    "correct": "Step is correct",
}

# ── Formula / final-answer extraction & matching ───────────────────────────────

_EQ_PATTERN = re.compile(r'[A-Za-zΔδη%]{1,8}(?:\s*\([^)]*\))?\s*=\s*[^=\n.;]{2,60}')
_NUM_PATTERN = re.compile(r'-?\d+(?:\.\d+)?(?:\s*[eE][-+]?\d+)?\s*[a-zA-Z°%/]{0,6}')

def extract_equations(text: str) -> List[str]:
    """Pulls out equation-like substrings (e.g. 'eta = 1 - T2/T1')."""
    if not text:
        return []
    return [m.group().strip() for m in _EQ_PATTERN.finditer(text)]

def extract_final_number(text: str) -> Optional[str]:
    """Heuristic: the LAST number (with optional unit) mentioned in the text
    is treated as the final answer - this is how solutions are usually
    written, with the result stated at the end."""
    if not text:
        return None
    matches = _NUM_PATTERN.findall(text)
    return matches[-1].strip() if matches else None

def _parse_number(token: str):
    m = re.match(r'(-?\d+(?:\.\d+)?)\s*([a-zA-Z°%/]*)', token.strip())
    if not m:
        return None
    return float(m.group(1)), m.group(2).lower()

def formula_mentioned(student_text: str, reference_text: str, expected_formula: str = "") -> bool:
    """
    True if the student appears to have written down the expected formula.
    Prefers an explicit `expected_formula` (rubric); otherwise extracts
    candidate equations from the reference (raw-data) text and checks for
    variable-token overlap with anything the student wrote as an equation.
    """
    student_eqs = extract_equations(student_text)
    if not student_eqs:
        return False  # student wrote no equation at all

    ref_eq_source = expected_formula or " ".join(extract_equations(reference_text))
    if not ref_eq_source:
        # No reference formula to check against - crediting any equation attempt
        return True

    ref_tokens = {t.lower() for t in re.findall(r'[A-Za-zΔδη]{1,8}', ref_eq_source) if len(t) <= 8}
    student_tokens = {t.lower() for t in re.findall(r'[A-Za-zΔδη]{1,8}', " ".join(student_eqs))}
    return len(ref_tokens & student_tokens) > 0

def final_answer_correct(student_text: str, reference_text: str,
                          expected_final_answer: str = "", tolerance: float = 0.02) -> bool:
    """
    True if the student's final numeric answer matches the expected one
    within a small relative tolerance (default 2%, to allow rounding).
    Prefers an explicit `expected_final_answer` (rubric); otherwise the
    last number in the reference (raw-data) text is used as the expected
    answer.
    """
    expected = expected_final_answer or extract_final_number(reference_text)
    if not expected:
        return True  # nothing to check against - don't penalize

    exp = _parse_number(expected)
    got = _parse_number(extract_final_number(student_text) or "")
    if not exp or not got:
        return False

    exp_val, _ = exp
    got_val, _ = got
    if exp_val == 0:
        return abs(got_val) < 1e-6
    return abs(got_val - exp_val) / abs(exp_val) <= tolerance

def grade_numerical(
    question: str,
    student_solution: str,
    reference_answer: str = "",
    rubric_steps: Optional[List[dict]] = None,
    expected_formula: str = "",
    expected_final_answer: str = "",
    subject: str = "Thermodynamics",
    max_marks: int = 10,
    model: str = None,
) -> dict:
    """
    Grade a numerical solution.

    `reference_answer` should be the question's raw-data-derived
    answer_key/source_chunk - used to extract the expected formula and
    final answer when those aren't explicitly given via
    `expected_formula` / `expected_final_answer`.

    Returns: {steps, ai_score, max_score, confidence, error_summary,
              formula_mentioned, final_answer_correct, deductions}
    """
    model = model or os.getenv("OLLAMA_MODEL", "mistral")

    rubric_text = ""
    if rubric_steps:
        rubric_text = "\n".join([
            f"Step {s['step']}: {s['description']} — Expected: {s['expected']} ({s['marks']} marks)"
            for s in rubric_steps
        ])

    step_result = None
    if OLLAMA_AVAILABLE:
        step_result = _llm_grade_steps(question, student_solution, rubric_text,
                                        reference_answer, subject, max_marks, model)
    if step_result is None:
        step_result = _fallback_grade(question, student_solution, rubric_steps, max_marks)

    # Step-level score = "marks for the rest" of the solution
    base_score = step_result["ai_score"]

    # Deterministic deductions, regardless of LLM availability
    has_formula = formula_mentioned(student_solution, reference_answer, expected_formula)
    answer_ok = final_answer_correct(student_solution, reference_answer, expected_final_answer)

    deductions = 0.0
    deduction_reasons = []
    if not has_formula:
        deductions += 1.0
        deduction_reasons.append("Formula/equation not mentioned (-1)")
    if not answer_ok:
        deductions += 1.0
        deduction_reasons.append("Final answer does not match expected value (-1)")

    ai_score = max(0.0, min(round(base_score - deductions, 1), max_marks))

    feedback = step_result.get("feedback", "")
    if deduction_reasons:
        feedback = (feedback + " " if feedback else "") + " ".join(deduction_reasons)

    explanation_lines = [
        f"Awarded {base_score}/{max_marks} marks for the working/method "
        f"(substitution, units, arithmetic, boundary conditions)."
    ]
    if not has_formula:
        explanation_lines.append("Deducted 1 mark: expected formula/equation was not written down.")
    if not answer_ok:
        explanation_lines.append("Deducted 1 mark: final numeric answer does not match the expected value.")
    if has_formula and answer_ok:
        explanation_lines.append("No deductions: formula was mentioned and the final answer matches.")
    explanation_lines.append(f"Total: {ai_score}/{max_marks}.")
    explanation = " ".join(explanation_lines)

    step_result.update({
        "ai_score": ai_score,
        "max_score": max_marks,
        "base_score": base_score,
        "formula_mentioned": has_formula,
        "final_answer_correct": answer_ok,
        "deductions": round(deductions, 1),
        "feedback": feedback,
        "explanation": explanation,
    })
    return step_result

def _llm_grade_steps(question, student_solution, rubric_text, reference_answer,
                      subject, max_marks, model) -> Optional[dict]:
    prompt = f"""You are an expert {subject} professor grading a numerical solution.

QUESTION: {question}

{"REFERENCE / MODEL SOLUTION (from raw source data):" + chr(10) + reference_answer if reference_answer else ""}

{"MARKING RUBRIC:" + chr(10) + rubric_text if rubric_text else ""}

STUDENT SOLUTION:
{student_solution}

Evaluate each step of the student's solution EXCLUDING whether the correct
formula was used and whether the final numeric answer is correct - those two
checks are handled separately. Focus on: substitution of values, unit
handling, arithmetic, and boundary/initial conditions. For each step:
1. What the student wrote
2. Whether it is correct
3. If wrong, which error category applies:
   - substitution_error: right formula, wrong values substituted
   - unit_error: wrong units or missing conversion
   - arithmetic_error: correct setup, calculation mistake
   - boundary_condition_error: wrong boundary/initial condition
4. Marks earned (out of step marks, or proportional if no rubric)

Respond ONLY in this exact JSON format:
{{
  "steps": [
    {{
      "step": 1,
      "description": "What this step calculates",
      "student_work": "What student wrote",
      "expected": "What the correct answer should be",
      "correct": true/false,
      "error_type": "correct" or one of the error categories,
      "marks": <max marks for this step>,
      "earned": <marks earned>,
      "explanation": "Brief explanation of error or confirmation of correctness"
    }}
  ],
  "total_earned": <sum of earned>,
  "total_marks": <sum of all step marks>,
  "feedback": "1-2 sentences on the working/method quality only",
  "confidence": <0.0-1.0>
}}

Output ONLY the JSON object above - no markdown code fences, no preamble, no text before or after it."""

    def _call_and_parse(p, temp):
        try:
            resp = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": p}],
                options={"temperature": temp},
            )
            text = resp["message"]["content"].strip()
            return parse_llm_json(text)
        except Exception:
            return None

    result = _call_and_parse(prompt, 0.2)
    if not result:
        # Mistral-7B-class models occasionally drop formatting on the first
        # attempt - retry once with a blunter instruction before falling
        # back to the heuristic grader.
        retry_prompt = prompt + "\n\nIMPORTANT: Output raw JSON only. Do not use ```json fences."
        result = _call_and_parse(retry_prompt, 0.1)

    if result:
        total_m = result.get("total_marks", max_marks) or max_marks
        total_e = result.get("total_earned", 0)
        result["ai_score"] = round((total_e / total_m) * max_marks, 1)
        result["max_score"] = max_marks
        result["error_summary"] = _summarize_errors(result.get("steps", []))
        return result
    return None

def _summarize_errors(steps: list) -> dict:
    summary = {k: 0 for k in ERROR_CATEGORIES}
    for s in steps:
        et = s.get("error_type", "correct")
        if et in summary:
            summary[et] += 1
    return summary

def _fallback_grade(question, student_solution, rubric_steps, max_marks) -> dict:
    """Heuristic grading when LLM unavailable."""
    # Count steps in student solution by looking for numbered lines or calculations
    lines = [l.strip() for l in student_solution.split("\n") if l.strip()]
    step_count = max(len(lines), 3)

    steps = []
    earned_total = 0
    marks_per_step = round(max_marks / step_count, 1)

    for i, line in enumerate(lines[:step_count]):
        # Heuristic: if line contains = and numbers, likely a calculation step
        has_calc = bool(re.search(r'=\s*[\d\.\-]', line))
        correct = has_calc  # assume lines with calculations are attempts
        earned = marks_per_step if correct else marks_per_step * 0.5
        earned_total += earned
        steps.append({
            "step": i + 1,
            "description": f"Step {i+1}",
            "student_work": line,
            "expected": "See model solution",
            "correct": correct,
            "error_type": "correct" if correct else "arithmetic_error",
            "marks": marks_per_step,
            "earned": round(earned, 1),
            "explanation": "Evaluated heuristically — LLM not available",
        })

    return {
        "steps": steps,
        "total_earned": round(earned_total, 1),
        "total_marks": max_marks,
        "ai_score": round(min(earned_total, max_marks), 1),
        "max_score": max_marks,
        "feedback": "Heuristic evaluation only — connect Ollama for full step-level grading.",
        "confidence": 0.4,
        "error_summary": _summarize_errors(steps),
    }
