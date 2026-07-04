"""
Stage 4 — Rubric-based evaluation
=================================
Each question type gets a tailored examiner prompt. The LLM must return a
strict JSON verdict mapped to the rubric. Fairness rules are baked into every
prompt:

  • never exact string matching — semantics, synonyms, equivalent definitions
  • accept alternate mathematically-correct methods
  • award partial marks step-wise
  • never invent deductions not grounded in the rubric

If no LLM is reachable (no API key, Ollama down) a deterministic
keyword + semantic-similarity fallback grades theory questions and a
step-detection heuristic grades numericals — clearly flagged so faculty
know the grading method.
"""

from __future__ import annotations
import json
import re
from typing import Dict, List, Optional

from evaluation.engine.llm import chat_json
from evaluation.engine.embeddings import similarity

_SYSTEM = (
    "You are a strict but fair university examiner for Mechanical Engineering. "
    "You grade EXACTLY according to the marking scheme given. "
    "You never require exact wording — you accept synonyms, equivalent "
    "definitions, alternate correct methods and equivalent diagrams. "
    "You award partial marks step-wise. You never deduct marks for things "
    "not covered by the rubric. You never hallucinate mistakes. "
    "You always answer with a single JSON object and nothing else."
)

_TYPE_GUIDANCE = {
    "theory": (
        "Evaluate: keyword/concept coverage, completeness, technical correctness, "
        "examples given, and explanation quality. Partial marks for partially "
        "correct answers."
    ),
    "numerical": (
        "Evaluate step-wise: (a) formula selection, (b) substitution, "
        "(c) calculation of intermediate steps, (d) final answer, (e) units, "
        "(f) significant figures. If the method is correct but the final answer "
        "is wrong due to arithmetic, award the method marks. If a wrong "
        "intermediate value is carried forward correctly, do not double-penalise."
    ),
    "diagram": (
        "The answer text contains an OCR transcription; diagrams appear as "
        "[DIAGRAM: ...] descriptions. Evaluate CONCEPTS not pixels: is the right "
        "diagram drawn, are labels present, are key components/annotations there, "
        "are proportions plausible. List missing components explicitly."
    ),
    "derivation": (
        "Evaluate the derivation: starting point, logical sequence of steps, "
        "correctness of each formula transformation, and the final expression. "
        "Award partial credit per correct step even if the final result is wrong."
    ),
    "flowchart": (
        "Evaluate the flowchart (may appear as [FLOWCHART: ...] or step lists): "
        "correct sequence, decision nodes present, sound logic, missing blocks."
    ),
    "graph": (
        "Evaluate the graph (may appear as [GRAPH: ...]): axes chosen correctly, "
        "labels present, correct trend/shape, correct plotting of key points."
    ),
    "mixed": (
        "This question mixes types (e.g. theory + numerical). Grade each part "
        "against the relevant rubric item."
    ),
}


def _default_rubric(q_type: str, max_marks: int) -> List[Dict]:
    """Sensible default rubric when faculty didn't provide one."""
    presets = {
        "numerical": [("Formula selection", 0.2), ("Method / substitution", 0.4), ("Calculation", 0.3), ("Units & final answer", 0.1)],
        "derivation": [("Starting point", 0.2), ("Logical steps", 0.5), ("Final expression", 0.3)],
        "diagram": [("Correct diagram", 0.4), ("Labels", 0.3), ("Completeness / annotations", 0.3)],
        "flowchart": [("Sequence", 0.4), ("Decision nodes", 0.3), ("Completeness", 0.3)],
        "graph": [("Axes & labels", 0.4), ("Trend / shape", 0.4), ("Plotting accuracy", 0.2)],
    }
    items = presets.get(q_type, [("Concept coverage", 0.5), ("Technical correctness", 0.3), ("Completeness & clarity", 0.2)])
    rubric, remaining = [], max_marks
    for i, (name, w) in enumerate(items):
        marks = round(max_marks * w, 1) if i < len(items) - 1 else round(remaining, 1)
        remaining = round(remaining - marks, 1)
        rubric.append({"criterion": name, "marks": marks})
    return rubric


def evaluate_answer(
    q_number: int,
    q_type: str,
    question: str,
    student_answer: str,
    reference_answer: str,
    max_marks: float,
    rubric: Optional[List[Dict]] = None,
    subject: str = "Mechanical Engineering",
    marking_instructions: str = "",
) -> Dict:
    """
    Grade one answer. Returns:
      {ai_score, max_score, rubric_mapping[], feedback, covered[], missing[],
       strengths[], weaknesses[], suggestions[], expected_answer,
       grading_method, model_confidence}
    """
    rubric = rubric or _default_rubric(q_type, int(max_marks))

    llm_result = _grade_with_llm(
        q_number, q_type, question, student_answer, reference_answer,
        max_marks, rubric, subject, marking_instructions,
    )
    if llm_result:
        return llm_result

    return _grade_fallback(q_type, question, student_answer, reference_answer, max_marks, rubric)


def _grade_with_llm(q_number, q_type, question, student_answer, reference_answer,
                    max_marks, rubric, subject, marking_instructions) -> Optional[Dict]:
    rubric_txt = "\n".join(f"  - {r['criterion']}: {r['marks']} marks" for r in rubric)
    extra = f"\nFaculty marking instructions: {marking_instructions}" if marking_instructions else ""

    prompt = f"""Subject: {subject}
Question {q_number} ({q_type}, maximum {max_marks} marks):
{question}

MARKING SCHEME (reference answer):
{reference_answer if reference_answer.strip() else '(none provided — grade on general correctness for this subject)'}

RUBRIC (grade against exactly these criteria):
{rubric_txt}
{extra}
Type-specific guidance: {_TYPE_GUIDANCE.get(q_type, _TYPE_GUIDANCE['theory'])}

STUDENT ANSWER (OCR transcription of handwriting — ignore OCR noise, do not
penalise spelling/transcription artifacts):
{student_answer[:6000]}

Return ONLY this JSON:
{{
  "rubric_mapping": [{{"criterion": "...", "max": <marks>, "awarded": <marks>, "reason": "..."}}],
  "awarded_marks": <total, must equal sum of rubric awarded>,
  "covered": ["concepts/steps the student got right"],
  "missing": ["required concepts/steps that are absent or wrong"],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "suggestions": ["how the student can improve"],
  "feedback": "2-3 sentence explanation of why these marks were awarded",
  "confidence": <0.0-1.0 how certain you are in this grade>
}}"""

    out = chat_json(prompt, system=_SYSTEM)
    if not out or "awarded_marks" not in out:
        return None

    try:
        awarded = float(out.get("awarded_marks", 0))
    except (TypeError, ValueError):
        return None
    awarded = max(0.0, min(float(max_marks), awarded))

    mapping = out.get("rubric_mapping") or []
    # keep rubric mapping honest: clamp each criterion to its max
    clean_map = []
    for r in mapping:
        try:
            mx = float(r.get("max", 0)); aw = max(0.0, min(mx, float(r.get("awarded", 0))))
            clean_map.append({"criterion": str(r.get("criterion", "")), "max": mx,
                              "awarded": aw, "reason": str(r.get("reason", ""))})
        except (TypeError, ValueError):
            continue
    if clean_map:
        total = sum(r["awarded"] for r in clean_map)
        if abs(total - awarded) > 0.51:
            awarded = min(float(max_marks), round(total, 1))

    return {
        "ai_score": round(awarded, 1),
        "max_score": float(max_marks),
        "rubric_mapping": clean_map or [{"criterion": "Overall", "max": float(max_marks), "awarded": awarded, "reason": out.get("feedback", "")}],
        "feedback": str(out.get("feedback", "")),
        "covered": [str(x) for x in (out.get("covered") or [])][:10],
        "missing": [str(x) for x in (out.get("missing") or [])][:10],
        "strengths": [str(x) for x in (out.get("strengths") or [])][:6],
        "weaknesses": [str(x) for x in (out.get("weaknesses") or [])][:6],
        "suggestions": [str(x) for x in (out.get("suggestions") or [])][:6],
        "expected_answer": reference_answer[:1200],
        "grading_method": "llm_rubric",
        "model_confidence": max(0.0, min(1.0, float(out.get("confidence", 0.75) or 0.75))),
    }


# ── Deterministic fallback (no LLM reachable) ─────────────────────────────────

_STOPWORDS = set("the a an and or of to in for with is are was were be been this that it as by on at from".split())


def _keywords(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _grade_fallback(q_type, question, student_answer, reference_answer, max_marks, rubric) -> Dict:
    if not student_answer.strip():
        return {
            "ai_score": 0.0, "max_score": float(max_marks),
            "rubric_mapping": [{"criterion": r["criterion"], "max": r["marks"], "awarded": 0.0,
                                "reason": "No answer content detected"} for r in rubric],
            "feedback": "No readable answer content was found for this question.",
            "covered": [], "missing": ["entire answer"], "strengths": [], "weaknesses": [],
            "suggestions": [], "expected_answer": reference_answer[:1200],
            "grading_method": "fallback", "model_confidence": 0.3,
        }

    sem = similarity(student_answer, reference_answer) if reference_answer.strip() else 0.0

    ref_kw = set(_keywords(reference_answer))
    stu_kw = set(_keywords(student_answer))
    kw_cov = len(ref_kw & stu_kw) / len(ref_kw) if ref_kw else 0.0

    # Rescale so a genuinely correct answer maps to high marks. MiniLM cosine
    # for a correct-but-reworded answer sits around 0.5-0.75, and 60% keyword
    # coverage already means the key concepts are present — both should score high.
    def _clamp(x):
        return max(0.0, min(1.0, x))

    sem_scaled = _clamp((sem - 0.20) / 0.50)   # 0.20→0, 0.70→full
    kw_scaled  = _clamp(kw_cov / 0.60)          # 60% coverage → full

    # numericals: reward visible formula/units/steps
    step_bonus = 0.0
    if q_type in ("numerical", "derivation"):
        has_eq = bool(re.search(r"=", student_answer))
        has_units = bool(re.search(r"\d\s*(MPa|kPa|kN|N|mm|m/s|rpm|W|J|K|°C|m)\b", student_answer))
        n_steps = len(re.findall(r"=", student_answer))
        step_bonus = 0.15 * has_eq + 0.10 * has_units + min(0.15, 0.03 * n_steps)

    # Lean on whichever signal is stronger, temper with the average.
    base = 0.65 * max(sem_scaled, kw_scaled) + 0.35 * ((sem_scaled + kw_scaled) / 2)
    score_frac = _clamp(base + step_bonus)

    # A real attempt (there is content and at least some topical match) should
    # never score 0 — the answer scheme is the master, faculty override refines.
    if len(student_answer.strip()) >= 40 and (sem >= 0.25 or kw_cov >= 0.10):
        score_frac = max(score_frac, 0.35)

    awarded = round(score_frac * float(max_marks), 1)

    covered = sorted(ref_kw & stu_kw)[:8]
    missing = sorted(ref_kw - stu_kw)[:8]
    return {
        "ai_score": awarded, "max_score": float(max_marks),
        "rubric_mapping": [{"criterion": r["criterion"], "max": r["marks"],
                            "awarded": round(score_frac * r["marks"], 1),
                            "reason": f"Proportional to semantic match ({sem:.0%}) and concept coverage ({kw_cov:.0%})"}
                           for r in rubric],
        "feedback": (f"Graded against the answer scheme by concept matching — "
                     f"{kw_cov:.0%} of the key points are present (semantic match {sem:.0%}). "
                     f"For sharper marking, enable an LLM (set an API key or run Ollama)."),
        "covered": covered, "missing": missing,
        "strengths": [f"Mentions: {', '.join(covered[:4])}"] if covered else [],
        "weaknesses": [f"Missing concepts: {', '.join(missing[:4])}"] if missing else [],
        "suggestions": ["Include the missing concepts listed above."] if missing else [],
        "expected_answer": reference_answer[:1200],
        "grading_method": "keyword_semantic",
        # scale confidence with match strength so strong answers aren't flagged
        "model_confidence": round(0.45 + 0.45 * score_frac, 2),
    }
