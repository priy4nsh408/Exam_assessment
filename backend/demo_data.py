"""
MechAssess demo data.

Replaces the old hardcoded MOCK_STUDENTS / MOCK_SUBMISSIONS / co_analytics
fixtures (which had hand-typed, made-up percentages with no connection to
the actual grading engine) with a small, deliberately-designed demo dataset
that's safe to show a professor: a fixed roster + fixed sample answers, but
every score is computed by actually calling evaluate_theory()/grade_numerical()
against the real seeded answer keys from seed_demo_data.py - so the numbers
on screen are genuinely what the grading engine produces, not invented.

This intentionally stays an in-memory module (no new SQLite tables) - the
question/answer-scheme data is still the real DB; only the student roster
and their sample submissions are demo fixtures, clearly marked as such.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.theory_evaluator import evaluate_theory
from evaluation.numerical_grader import grade_numerical
from generation.langgraph_pipeline import get_question_by_id

import seed_demo_data as _seed

# ── Demo student roster ──────────────────────────────────────────────────────
# Same names/USNs the prototype has used throughout (RVCE ME, sections A/B/C),
# kept for continuity - the fix here is the SCORES, not the roster identity.

DEMO_STUDENTS = [
    {"id": "ST-001", "usn": "1RV23ME001", "name": "Arjun Sharma", "section": "ME-A"},
    {"id": "ST-002", "usn": "1RV23ME002", "name": "Priya Nair", "section": "ME-A"},
    {"id": "ST-003", "usn": "1RV23ME003", "name": "Rohan Das", "section": "ME-A"},
    {"id": "ST-004", "usn": "1RV23ME004", "name": "Kavitha Rao", "section": "ME-B"},
    {"id": "ST-005", "usn": "1RV23ME005", "name": "Suresh M", "section": "ME-B"},
]

# Per-student sample answers, deliberately varied (strong / weak / mixed) so
# the demo shows the grading engine producing a realistic spread - not so
# every student looks identical, but also not randomized run-to-run.
# Keys are answer "quality tiers" already authored in seed_demo_data.py.
_THEORY_TIER_BY_STUDENT = {
    "ST-001": "good",
    "ST-002": "good",
    "ST-003": "poor",
    "ST-004": "good",
    "ST-005": "poor",
}
_NUMERICAL_TIER_BY_STUDENT = {
    "ST-001": "good",
    "ST-002": "good",
    "ST-003": "wrong_final",
    "ST-004": "no_formula",
    "ST-005": "good",
}

_SUBMISSION_BASE_TIME = datetime(2026, 5, 10, 9, 0, 0)


def _build_submissions():
    """
    One theory + one numerical submission per demo student, against the real
    seeded questions (Q-DEMO-THEORY / Q-DEMO-NUMERICAL). No drawing
    submission is synthesized here - per the project brief, drawing grading
    needs an actual uploaded image and there's no synthetic image demo path
    yet, so it stays out of this dataset rather than faking a result for it.
    """
    submissions = []
    sid = 1
    for student in DEMO_STUDENTS:
        theory_tier = _THEORY_TIER_BY_STUDENT.get(student["id"], "poor")
        theory_text = _seed.SAMPLE_ANSWERS["theory"][theory_tier]
        submissions.append({
            "id": f"S-{sid:03d}",
            "studentId": student["id"],
            "questionId": "Q-DEMO-THEORY",
            "type": "theory",
            "content": theory_text,
            "submittedAt": (_SUBMISSION_BASE_TIME + timedelta(minutes=sid)).isoformat() + "Z",
            "status": "graded",
        })
        sid += 1

        num_tier = _NUMERICAL_TIER_BY_STUDENT.get(student["id"], "good")
        num_text = _seed.SAMPLE_ANSWERS["numerical"][num_tier]
        submissions.append({
            "id": f"S-{sid:03d}",
            "studentId": student["id"],
            "questionId": "Q-DEMO-NUMERICAL",
            "type": "numerical",
            "content": num_text,
            "submittedAt": (_SUBMISSION_BASE_TIME + timedelta(minutes=sid)).isoformat() + "Z",
            "status": "graded",
        })
        sid += 1
    return submissions


DEMO_SUBMISSIONS = _build_submissions()

DEMO_EXAMS = [
    {
        "id": "EX-DEMO-001",
        "title": "Thermodynamics — Demo Assessment (Units 1 & 2)",
        "subject": "Thermodynamics", "totalMarks": 20, "duration": 60,
        "questions": ["Q-DEMO-THEORY", "Q-DEMO-NUMERICAL"],
        "createdAt": _SUBMISSION_BASE_TIME.isoformat() + "Z",
        "status": "published",
    },
]


def _ensure_demo_questions_seeded():
    """Idempotently seed the demo questions/answer schemes if they aren't
    already in the DB (e.g. fresh clone that hasn't run seed_demo_data.py)."""
    if not get_question_by_id("Q-DEMO-THEORY"):
        _seed.seed()


_grade_cache = None


def _grade_all_demo_submissions():
    """
    Runs the real evaluators (evaluate_theory / grade_numerical) against
    every demo submission, against the real seeded answer key for its
    question. Cached for the process lifetime since the underlying demo
    data never changes - avoids re-running embeddings on every request.
    """
    global _grade_cache
    if _grade_cache is not None:
        return _grade_cache

    _ensure_demo_questions_seeded()
    results = {}
    for sub in DEMO_SUBMISSIONS:
        question = get_question_by_id(sub["questionId"])
        if not question:
            continue
        reference = question.get("answer_key") or question.get("source_chunk") or ""
        max_marks = question.get("marks", 10)

        if sub["type"] == "theory":
            r = evaluate_theory(
                question=question["text"], student_answer=sub["content"],
                reference_answer=reference, subject=question.get("subject", ""),
                max_marks=max_marks,
            )
            score_pct = round((r["ai_score"] / max_marks) * 100) if max_marks else 0
        else:
            r = grade_numerical(
                question=question["text"], student_solution=sub["content"],
                reference_answer=reference, subject=question.get("subject", ""),
                max_marks=max_marks,
            )
            score_pct = round((r["ai_score"] / max_marks) * 100) if max_marks else 0

        results[sub["id"]] = {
            "studentId": sub["studentId"],
            "questionId": sub["questionId"],
            "type": sub["type"],
            "co": question.get("co", "CO1"),
            "ai_score": r["ai_score"],
            "max_score": max_marks,
            "score_pct": max(0, min(100, score_pct)),
            "confidence": r.get("confidence", 0.6),
        }

    _grade_cache = results
    return results


def get_demo_students_with_scores():
    """
    Returns the demo roster with real per-type (theory/numerical/drawing)
    and per-CO percentage scores attached, computed from
    _grade_all_demo_submissions() - i.e. what Students.tsx renders in the
    gradebook table. Drawing has no demo submission (see _build_submissions
    docstring), so it's reported as None rather than a fabricated number.
    """
    grades = _grade_all_demo_submissions()
    by_student = {}
    for g in grades.values():
        by_student.setdefault(g["studentId"], []).append(g)

    out = []
    for student in DEMO_STUDENTS:
        sub_grades = by_student.get(student["id"], [])
        theory = next((g["score_pct"] for g in sub_grades if g["type"] == "theory"), None)
        numerical = next((g["score_pct"] for g in sub_grades if g["type"] == "numerical"), None)
        drawing = None  # no demo drawing submission yet - see module docstring

        co_scores = {}
        for g in sub_grades:
            co_scores.setdefault(g["co"], []).append(g["score_pct"])
        co_avgs = {co: round(sum(v) / len(v)) for co, v in co_scores.items()}

        present_scores = [v for v in (theory, numerical) if v is not None]
        avg = round(sum(present_scores) / len(present_scores)) if present_scores else None

        out.append({
            "usn": student["usn"], "name": student["name"], "section": student["section"],
            "theory": theory, "numerical": numerical, "drawing": drawing,
            "co1": co_avgs.get("CO1"), "co2": co_avgs.get("CO2"), "co3": co_avgs.get("CO3"),
            "co4": co_avgs.get("CO4"), "co5": co_avgs.get("CO5"),
            "avg": avg,
        })
    return out


CO_DESCRIPTIONS = {
    "CO1": "Apply laws of thermodynamics to analyze engineering systems",
    "CO2": "Analyze power cycles and refrigeration systems",
    "CO3": "Solve problems in strength of materials and structural analysis",
    "CO4": "Apply fluid mechanics principles to flow analysis",
    "CO5": "Interpret and produce engineering drawings per IS standards",
}


def get_demo_co_analytics():
    """
    CO attainment computed live from the real demo grades (not hardcoded
    percentages). Only COs that actually appear in a demo question have a
    real computed value; the rest are reported with null attainment rather
    than an invented number, since this demo dataset doesn't cover them.
    """
    grades = _grade_all_demo_submissions()
    by_co = {}
    for g in grades.values():
        by_co.setdefault(g["co"], []).append(g["score_pct"])

    total_students = len(DEMO_STUDENTS)
    co_data = []
    all_attainments = []
    for co in ("CO1", "CO2", "CO3", "CO4", "CO5"):
        scores = by_co.get(co, [])
        if scores:
            avg_attainment = round(sum(scores) / len(scores), 1)
            students_achieved = sum(1 for s in scores if s >= 70)
            all_attainments.append(avg_attainment)
        else:
            avg_attainment = None
            students_achieved = None
        co_data.append({
            "co": co,
            "description": CO_DESCRIPTIONS.get(co, ""),
            "averageAttainment": avg_attainment,
            "studentsAchieved": students_achieved,
            "totalStudents": total_students if scores else None,
            "target": 70,
            "isDemoComputed": bool(scores),
        })

    overall = round(sum(all_attainments) / len(all_attainments), 1) if all_attainments else None
    return {"co_analytics": co_data, "overall_attainment": overall, "target": 70}


def get_demo_stats():
    """Real counts/derived numbers for the dashboard, instead of hand-typed
    placeholders like avgCOAttainment=76.8 or timeSavedHours=186."""
    analytics = get_demo_co_analytics()
    pending = sum(1 for s in DEMO_SUBMISSIONS if s["status"] == "pending")
    graded = sum(1 for s in DEMO_SUBMISSIONS if s["status"] == "graded")
    return {
        "activeExams": sum(1 for e in DEMO_EXAMS if e["status"] == "published"),
        "submissionsPending": pending,
        "avgCOAttainment": analytics["overall_attainment"],
        "totalStudents": len(DEMO_STUDENTS),
        "gradedToday": graded,
    }


def get_demo_grade_result(submission_id: str):
    """Looks up the cached real grading result for a demo submission id, in
    the shape /api/submissions/{id}/grade already returns."""
    grades = _grade_all_demo_submissions()
    g = grades.get(submission_id)
    if not g:
        return None
    return {
        "submissionId": submission_id,
        "aiScore": g["ai_score"],
        "maxScore": g["max_score"],
        "confidence": g["confidence"],
        "co": g["co"],
        "scorePct": g["score_pct"],
    }
