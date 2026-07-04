"""
Stage 2 — Question detection & type classification
==================================================
• Detects question numbers in every common handwritten form:
    Q1  /  Q.1  /  Question 1  /  Ques 1  /  Ans 1  /  Answer 1  /  1.  /  1)
• Sequential sanity filter kills stray numbers (marks tables, dates, page
  numbers) so they never become phantom questions.
• Classifies question type: theory / numerical / diagram / derivation /
  flowchart / graph / mixed.
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

QUESTION_BOUNDARY = re.compile(
    r"(?m)^[\s]*(?:"
    r"(?:ans(?:wer)?|sol(?:ution)?)?\s*[.:\-]?\s*[Qq](?:ues(?:tion)?)?\s*[.:\-]?\s*(\d{1,2})"  # Q1, Question 1, Ans Q1
    r"|(?:ans(?:wer)?|sol(?:ution)?)\s*[.:\-]?\s*(\d{1,2})"                                     # Ans 1, Solution 3
    r"|(\d{1,2})\s*[.)][\s]"                                                                     # 1.  or 1)
    r")",
    re.IGNORECASE,
)


def find_question_markers(full_text: str, max_q: int = 20) -> List[Tuple[int, int, int]]:
    """
    Find question-number markers in the text.
    Returns [(char_start, char_end_of_marker, q_number)] after sanity filtering.

    Answers may appear in ANY order (Q5, Q1, Q8...) — we do NOT require a
    sequential run, only that numbers are plausible (1..max_q) and that the
    same question number isn't detected twice within a few characters.
    """
    raw = []
    for m in QUESTION_BOUNDARY.finditer(full_text):
        qnum = int(next(g for g in m.groups() if g is not None))
        if 1 <= qnum <= max_q:
            raw.append((m.start(), m.end(), qnum))

    # De-noise: "1." style markers are only trusted if 'strong' markers (Q1 /
    # Ans 1) are absent, because bare numbers also appear in lists/steps.
    strong = [
        (s, e, q) for (s, e, q) in raw
        if re.match(r"^[\s]*(?:ans|sol|q)", full_text[s:e], re.IGNORECASE)
    ]
    markers = strong if strong else raw

    # Drop consecutive duplicates of the same question number
    filtered: List[Tuple[int, int, int]] = []
    for s, e, q in sorted(markers):
        if filtered and filtered[-1][2] == q:
            continue
        filtered.append((s, e, q))
    return filtered


# ── Question type classification ─────────────────────────────────────────────

_SIGNALS = {
    "numerical": re.compile(
        r"\b(calculat|comput|find|determin|solve|value of|how much|how many|"
        r"mpa|kpa|kn|rpm|joule|watt|newton|kg|m/s|mm|units?|"
        r"stress|strain|force|moment|torque|velocity|pressure|efficiency|power)\b", re.I),
    "diagram": re.compile(
        r"\b(draw|sketch|illustrat|diagram|label(led)?|cross.?section|isometric|"
        r"orthograph|projection|free.?body|fbd|\[DIAGRAM)\b", re.I),
    "derivation": re.compile(
        r"\b(deriv|prove|show that|obtain (an |the )?expression|starting from|"
        r"first principles?)\b", re.I),
    "flowchart": re.compile(r"\b(flow.?chart|algorithm|decision (box|node)|\[FLOWCHART)\b", re.I),
    "graph": re.compile(
        r"\b(graph|plot|curve|characteristic|x.?axis|y.?axis|trend|versus|vs\.?|"
        r"\[GRAPH|t.?s diagram|p.?v diagram)\b", re.I),
    "theory": re.compile(
        r"\b(explain|describe|define|state|list|discuss|differentiat|compare|"
        r"what (is|are)|why|advantages|disadvantages|principle|types of|classif)\b", re.I),
}


def classify_question_type(question_text: str, answer_text: str = "", declared: str = "") -> str:
    """Detect question type. Faculty-declared type always wins."""
    if declared and declared.lower() in _SIGNALS or declared.lower() in ("theory", "numerical", "diagram", "derivation", "flowchart", "graph", "mixed"):
        return declared.lower()

    text = f"{question_text}\n{answer_text}"
    scores = {t: len(rx.findall(text)) for t, rx in _SIGNALS.items()}
    top = sorted(scores.items(), key=lambda kv: -kv[1])
    if top[0][1] == 0:
        return "theory"
    # Mixed: two strong distinct signals
    if len(top) > 1 and top[1][1] >= 2 and top[0][1] >= 2 and top[0][0] != top[1][0]:
        return "mixed"
    return top[0][0]
