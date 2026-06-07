"""
Numerical step-level grader using LLM with chain-of-thought prompting.
Classifies errors into 5 categories and assigns partial credit per step.
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

ERROR_CATEGORIES = {
    "formula_error": "Wrong formula or equation used",
    "substitution_error": "Correct formula but wrong value substituted",
    "unit_error": "Incorrect units or missing unit conversion",
    "arithmetic_error": "Correct setup but arithmetic/calculation mistake",
    "boundary_condition_error": "Wrong boundary or initial condition applied",
    "correct": "Step is correct",
}

def grade_numerical(
    question: str,
    student_solution: str,
    rubric_steps: Optional[List[dict]] = None,
    subject: str = "Thermodynamics",
    max_marks: int = 10,
    model: str = None,
) -> dict:
    """
    Grade a numerical solution step by step.

    rubric_steps (optional): list of {step, description, expected, marks}
    Returns: {steps, ai_score, max_score, confidence, error_summary}
    """
    model = model or os.getenv("OLLAMA_MODEL", "mistral")

    rubric_text = ""
    if rubric_steps:
        rubric_text = "\n".join([
            f"Step {s['step']}: {s['description']} — Expected: {s['expected']} ({s['marks']} marks)"
            for s in rubric_steps
        ])

    prompt = f"""You are an expert {subject} professor grading a numerical solution.

QUESTION: {question}

{"MARKING RUBRIC:" + chr(10) + rubric_text if rubric_text else ""}

STUDENT SOLUTION:
{student_solution}

Evaluate each step of the student's solution. For each step you identify:
1. What the student wrote
2. Whether it is correct
3. If wrong, which error category applies:
   - formula_error: wrong equation used
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
      "error_type": "correct" or one of the 5 error categories,
      "marks": <max marks for this step>,
      "earned": <marks earned>,
      "explanation": "Brief explanation of error or confirmation of correctness"
    }}
  ],
  "total_earned": <sum of earned>,
  "total_marks": <sum of all step marks>,
  "feedback": "2-3 sentences of overall feedback",
  "confidence": <0.0-1.0>
}}"""

    if OLLAMA_AVAILABLE:
        try:
            resp = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
            text = resp["message"]["content"].strip()
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                # Normalize score to max_marks
                total_m = result.get("total_marks", max_marks) or max_marks
                total_e = result.get("total_earned", 0)
                ai_score = round((total_e / total_m) * max_marks, 1)
                result["ai_score"] = ai_score
                result["max_score"] = max_marks
                result["error_summary"] = _summarize_errors(result.get("steps", []))
                return result
        except Exception:
            pass

    # Fallback: return structured mock
    return _fallback_grade(question, student_solution, rubric_steps, max_marks)

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
