"""
Stage 6 — Reports & analytics
=============================
  student_report(report)   — per-student view (question-wise marks, feedback)
  faculty_report(reports)  — low-confidence questions, common mistakes,
                             most-missed concepts, review queue
  class_analytics(reports) — average, distribution, difficulty,
                             question-wise & topic-wise performance
"""

from __future__ import annotations
from collections import Counter, defaultdict
from typing import Dict, List


def student_report(report: Dict) -> Dict:
    return {
        "student_name": report.get("student_name", ""),
        "subject": report.get("subject", ""),
        "exam_name": report.get("exam_name", ""),
        "total": report.get("total_score", 0),
        "max_total": report.get("max_total", 0),
        "percentage": report.get("percentage", 0),
        "question_wise": [
            {
                "q_number": a["q_number"],
                "type": a.get("q_type", ""),
                "marks": a.get("ai_score", 0),
                "max": a.get("max_score", 0),
                "feedback": a.get("feedback", ""),
                "strengths": a.get("strengths", []),
                "weaknesses": a.get("weaknesses", []),
                "suggestions": a.get("suggestions", []),
            }
            for a in report.get("answers", [])
        ],
        "unanswered": report.get("unanswered_questions", []),
    }


def faculty_report(reports: List[Dict]) -> Dict:
    """Aggregate across evaluated scripts: what needs faculty attention."""
    review_queue = []
    q_conf: Dict[int, List[float]] = defaultdict(list)
    missed_concepts: Counter = Counter()
    mistakes: Counter = Counter()

    for r in reports:
        for a in r.get("answers", []):
            qn = a.get("q_number", 0)
            q_conf[qn].append(a.get("confidence", 0))
            for m in a.get("missing", []):
                missed_concepts[m.strip().lower()[:60]] += 1
            for w in a.get("weaknesses", []):
                mistakes[w.strip().lower()[:80]] += 1
            if a.get("requires_faculty_review"):
                review_queue.append({
                    "student": r.get("student_name", ""),
                    "result_id": r.get("result_id", ""),
                    "q_number": qn,
                    "confidence": a.get("confidence", 0),
                    "illegible": a.get("illegible", False),
                    "reason": "illegible handwriting" if a.get("illegible") else "confidence below threshold",
                })

    lowest_conf = sorted(
        ({"q_number": q, "avg_confidence": round(sum(c) / len(c), 3)} for q, c in q_conf.items() if c),
        key=lambda x: x["avg_confidence"],
    )

    return {
        "scripts": len(reports),
        "review_queue": sorted(review_queue, key=lambda x: x["confidence"]),
        "lowest_confidence_questions": lowest_conf[:10],
        "common_mistakes": [{"mistake": m, "count": c} for m, c in mistakes.most_common(10)],
        "most_missed_concepts": [{"concept": m, "count": c} for m, c in missed_concepts.most_common(10)],
    }


def class_analytics(reports: List[Dict]) -> Dict:
    valid = [r for r in reports if r.get("max_total")]
    if not valid:
        return {"scripts": 0}

    pcts = [r.get("percentage", 0) for r in valid]
    dist = Counter()
    for p in pcts:
        bucket = f"{int(p // 10) * 10}-{int(p // 10) * 10 + 9}"
        dist[bucket] += 1

    q_perf: Dict[int, List[float]] = defaultdict(list)
    for r in valid:
        for a in r.get("answers", []):
            if a.get("max_score"):
                q_perf[a["q_number"]].append(a.get("ai_score", 0) / a["max_score"])

    question_wise = [
        {
            "q_number": q,
            "avg_pct": round(sum(v) / len(v) * 100, 1),
            "attempts": len(v),
            "difficulty": "hard" if sum(v) / len(v) < 0.4 else "medium" if sum(v) / len(v) < 0.7 else "easy",
        }
        for q, v in sorted(q_perf.items())
    ]

    return {
        "scripts": len(valid),
        "average_pct": round(sum(pcts) / len(pcts), 1),
        "highest_pct": max(pcts),
        "lowest_pct": min(pcts),
        "distribution": dict(sorted(dist.items())),
        "question_wise": question_wise,
        "hardest_questions": [q for q in question_wise if q["difficulty"] == "hard"],
    }
