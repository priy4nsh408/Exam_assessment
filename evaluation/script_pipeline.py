"""
Compatibility adapter — the real pipeline lives in evaluation/engine/.

Keeps the historical entry points used by backend/main.py:
  evaluate_answer_script(file_path, subject, max_marks_per_q, exam_questions, ...)
  evaluate_multiple_scripts(file_entries, ...)
"""

from __future__ import annotations
from typing import Dict, List, Optional

from evaluation.engine.pipeline import evaluate_script
from evaluation.engine.reports import class_analytics, faculty_report  # noqa: F401


def evaluate_answer_script(
    file_path: str,
    subject: str = "Mechanical Engineering",
    max_marks_per_q: int = 10,
    exam_questions: Optional[List[Dict]] = None,
    student_name: str = "",
    student_usn: str = "",
    exam: Optional[Dict] = None,
) -> Dict:
    exam_payload = dict(exam or {})
    exam_payload.setdefault("subject", subject)
    if exam_questions and not exam_payload.get("questions"):
        exam_payload["questions"] = exam_questions
    return evaluate_script(
        file_path=file_path,
        exam=exam_payload,
        student_name=student_name,
        student_usn=student_usn,
        max_marks_per_q=max_marks_per_q,
    )


def evaluate_multiple_scripts(
    file_entries: List[Dict],
    subject: str = "Mechanical Engineering",
    max_marks_per_q: int = 10,
    exam_questions: Optional[List[Dict]] = None,
    exam: Optional[Dict] = None,
) -> Dict:
    reports = []
    for entry in file_entries:
        try:
            r = evaluate_answer_script(
                file_path=entry["file_path"],
                subject=subject,
                max_marks_per_q=max_marks_per_q,
                exam_questions=exam_questions,
                student_name=entry.get("student_name", ""),
                student_usn=entry.get("student_usn", ""),
                exam=exam,
            )
            r["error"] = None
        except Exception as exc:
            r = {
                "student_name": entry.get("student_name", ""),
                "student_usn": entry.get("student_usn", ""),
                "file_path": entry.get("file_path", ""),
                "error": str(exc),
                "total_score": 0, "max_total": 0, "percentage": 0, "answers": [],
            }
        reports.append(r)

    valid = [r for r in reports if not r.get("error")]
    analytics = class_analytics(valid)
    pass_count = sum(1 for r in valid if r.get("percentage", 0) >= 40)

    return {
        "reports": reports,
        "total_students": len(reports),
        "class_avg": analytics.get("average_pct", 0.0),
        "pass_count": pass_count,
        "fail_count": len(valid) - pass_count,
        "subject": subject,
        "analytics": analytics,
        "faculty_report": faculty_report(valid),
    }
