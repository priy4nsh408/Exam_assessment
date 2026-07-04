"""
Evaluation API v2 — exam-centric closed-loop workflow.

  POST   /api/eval/exams                    create exam (scheme, rubrics, instructions)
  GET    /api/eval/exams                    list exams
  GET    /api/eval/exams/{exam_id}          full exam definition
  DELETE /api/eval/exams/{exam_id}
  POST   /api/eval/exams/{exam_id}/evaluate upload student script PDF → full AI report
  POST   /api/eval/results/{id}/override    faculty override (logged)
  GET    /api/eval/results/{id}/overrides   audit log
  GET    /api/eval/reports/faculty          review queue, common mistakes, missed concepts
  GET    /api/eval/reports/class            class analytics
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

router = APIRouter()

_DB = Path(__file__).parent.parent / "data" / "eval_results.db"
_UPLOADS = Path(__file__).parent.parent / "data" / "uploads"


def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB))
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS eval_exams (
            id          TEXT PRIMARY KEY,
            exam_name   TEXT,
            subject     TEXT,
            semester    TEXT,
            max_marks   REAL,
            marking_instructions TEXT,
            questions_json TEXT,
            created_at  TEXT
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id              TEXT PRIMARY KEY,
            student_name    TEXT,
            student_usn     TEXT,
            subject         TEXT,
            total_score     REAL,
            max_total       REAL,
            percentage      REAL,
            questions_evaluated INTEGER,
            report_json     TEXT,
            evaluated_at    TEXT
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS eval_overrides (
            id          TEXT PRIMARY KEY,
            result_id   TEXT,
            q_number    INTEGER,
            action      TEXT,      -- approve / reject / adjust_marks / rewrite_feedback
            old_marks   REAL,
            new_marks   REAL,
            old_feedback TEXT,
            new_feedback TEXT,
            faculty     TEXT,
            reason      TEXT,
            created_at  TEXT
        )""")
    c.commit()
    return c


# ── Exam management ───────────────────────────────────────────────────────────

class RubricItem(BaseModel):
    criterion: str
    marks: float


class ExamQuestion(BaseModel):
    q_number: int
    question: str = ""
    reference_answer: str = ""
    max_marks: float = 10
    type: str = ""                       # theory/numerical/diagram/derivation/flowchart/graph/mixed ('' = auto)
    rubric: Optional[List[RubricItem]] = None
    marking_instructions: str = ""


class ExamCreate(BaseModel):
    exam_name: str
    subject: str
    semester: str = ""
    max_marks: float = 0                 # 0 = sum of question marks
    marking_instructions: str = ""       # global numerical/diagram instructions
    questions: List[ExamQuestion] = Field(default_factory=list)


@router.post("/api/eval/exams")
async def create_eval_exam(body: ExamCreate):
    exam_id = f"EVX-{uuid.uuid4().hex[:8].upper()}"
    qs = [q.model_dump() for q in body.questions]
    max_marks = body.max_marks or sum(q["max_marks"] for q in qs)
    c = _conn()
    c.execute(
        "INSERT INTO eval_exams VALUES (?,?,?,?,?,?,?,?)",
        (exam_id, body.exam_name, body.subject, body.semester, max_marks,
         body.marking_instructions, json.dumps(qs), datetime.utcnow().isoformat() + "Z"),
    )
    c.commit(); c.close()
    return {"id": exam_id, "exam_name": body.exam_name, "subject": body.subject,
            "max_marks": max_marks, "questions": len(qs)}


@router.get("/api/eval/exams")
async def list_eval_exams():
    c = _conn()
    rows = c.execute(
        "SELECT id, exam_name, subject, semester, max_marks, created_at, questions_json "
        "FROM eval_exams ORDER BY created_at DESC").fetchall()
    c.close()
    return {"exams": [{
        "id": r["id"], "exam_name": r["exam_name"], "subject": r["subject"],
        "semester": r["semester"], "max_marks": r["max_marks"],
        "created_at": r["created_at"],
        "question_count": len(json.loads(r["questions_json"] or "[]")),
    } for r in rows]}


def _load_exam(exam_id: str) -> dict:
    c = _conn()
    r = c.execute("SELECT * FROM eval_exams WHERE id=?", (exam_id,)).fetchone()
    c.close()
    if not r:
        raise HTTPException(status_code=404, detail="Exam not found")
    return {
        "id": r["id"], "exam_name": r["exam_name"], "subject": r["subject"],
        "semester": r["semester"], "max_marks": r["max_marks"],
        "marking_instructions": r["marking_instructions"] or "",
        "questions": json.loads(r["questions_json"] or "[]"),
        "created_at": r["created_at"],
    }


@router.get("/api/eval/exams/{exam_id}")
async def get_eval_exam(exam_id: str):
    return _load_exam(exam_id)


@router.delete("/api/eval/exams/{exam_id}")
async def delete_eval_exam(exam_id: str):
    c = _conn()
    c.execute("DELETE FROM eval_exams WHERE id=?", (exam_id,))
    c.commit(); c.close()
    return {"deleted": exam_id}


# ── Script evaluation against an exam ─────────────────────────────────────────

def _save_result(report: dict) -> str:
    result_id = uuid.uuid4().hex[:12]
    c = _conn()
    c.execute(
        "INSERT INTO eval_results VALUES (?,?,?,?,?,?,?,?,?,?)",
        (result_id, report.get("student_name", ""), report.get("student_usn", ""),
         report.get("subject", ""), report.get("total_score", 0), report.get("max_total", 0),
         report.get("percentage", 0), report.get("questions_evaluated", 0),
         json.dumps(report), datetime.utcnow().isoformat() + "Z"),
    )
    c.commit(); c.close()
    return result_id


@router.post("/api/eval/exams/{exam_id}/evaluate")
async def evaluate_against_exam(
    exam_id: str,
    file: UploadFile = File(...),
    student_name: str = Form(""),
    student_usn: str = Form(""),
):
    exam = _load_exam(exam_id)
    from evaluation.engine.pipeline import evaluate_script

    _UPLOADS.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "script.pdf").suffix or ".pdf"
    save_path = str(_UPLOADS / f"script_{uuid.uuid4().hex}{suffix}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        report = evaluate_script(
            file_path=save_path, exam=exam,
            student_name=student_name or (file.filename or ""),
            student_usn=student_usn,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    report["exam_id"] = exam_id
    report["result_id"] = _save_result(report)
    return report


# ── Faculty override (every override is logged) ───────────────────────────────

class OverrideRequest(BaseModel):
    q_number: int
    action: str                      # approve / reject / adjust_marks / rewrite_feedback
    new_marks: Optional[float] = None
    new_feedback: Optional[str] = None
    faculty: str = ""
    reason: str = ""


@router.post("/api/eval/results/{result_id}/override")
async def override_result(result_id: str, body: OverrideRequest):
    c = _conn()
    row = c.execute("SELECT report_json FROM eval_results WHERE id=?", (result_id,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(status_code=404, detail="Result not found")

    report = json.loads(row["report_json"])
    ans = next((a for a in report.get("answers", []) if a.get("q_number") == body.q_number), None)
    if not ans:
        c.close()
        raise HTTPException(status_code=404, detail=f"Q{body.q_number} not in this result")

    old_marks = float(ans.get("ai_score", 0))
    old_feedback = ans.get("feedback", "")

    if body.action == "adjust_marks":
        if body.new_marks is None:
            c.close()
            raise HTTPException(status_code=400, detail="new_marks required")
        ans["ai_score"] = max(0.0, min(float(ans.get("max_score", body.new_marks)), float(body.new_marks)))
        ans["overridden"] = True
    elif body.action == "rewrite_feedback":
        if body.new_feedback is None:
            c.close()
            raise HTTPException(status_code=400, detail="new_feedback required")
        ans["feedback"] = body.new_feedback
        ans["overridden"] = True
    elif body.action == "approve":
        ans["faculty_approved"] = True
        ans["requires_faculty_review"] = False
    elif body.action == "reject":
        ans["faculty_rejected"] = True
        ans["requires_faculty_review"] = True
    else:
        c.close()
        raise HTTPException(status_code=400, detail="action must be approve/reject/adjust_marks/rewrite_feedback")

    # recompute totals
    total = round(sum(float(a.get("ai_score", 0)) for a in report.get("answers", [])), 1)
    report["total_score"] = total
    report["percentage"] = round(total / report["max_total"] * 100, 1) if report.get("max_total") else 0

    override_id = uuid.uuid4().hex[:12]
    entry = {
        "id": override_id, "result_id": result_id, "q_number": body.q_number,
        "action": body.action, "old_marks": old_marks,
        "new_marks": float(ans.get("ai_score", old_marks)),
        "old_feedback": old_feedback, "new_feedback": ans.get("feedback", ""),
        "faculty": body.faculty, "reason": body.reason,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    report.setdefault("overrides", []).append(entry)

    c.execute("INSERT INTO eval_overrides VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (override_id, result_id, body.q_number, body.action, old_marks,
               entry["new_marks"], old_feedback, entry["new_feedback"],
               body.faculty, body.reason, entry["created_at"]))
    c.execute("UPDATE eval_results SET report_json=?, total_score=?, percentage=? WHERE id=?",
              (json.dumps(report), total, report["percentage"], result_id))
    c.commit(); c.close()
    return {"override": entry, "total_score": total, "percentage": report["percentage"]}


@router.get("/api/eval/results/{result_id}/overrides")
async def list_overrides(result_id: str):
    c = _conn()
    rows = c.execute("SELECT * FROM eval_overrides WHERE result_id=? ORDER BY created_at",
                     (result_id,)).fetchall()
    c.close()
    return {"overrides": [dict(r) for r in rows]}


# ── Reports ───────────────────────────────────────────────────────────────────

def _all_reports(subject: str = "") -> list:
    c = _conn()
    rows = c.execute("SELECT id, report_json FROM eval_results").fetchall()
    c.close()
    out = []
    for r in rows:
        try:
            rep = json.loads(r["report_json"])
            rep["result_id"] = r["id"]
            if not subject or rep.get("subject", "").lower() == subject.lower():
                out.append(rep)
        except Exception:
            continue
    return out


@router.get("/api/eval/reports/faculty")
async def faculty_report_api(subject: str = ""):
    from evaluation.engine.reports import faculty_report
    return faculty_report(_all_reports(subject))


@router.get("/api/eval/reports/class")
async def class_report_api(subject: str = ""):
    from evaluation.engine.reports import class_analytics
    return class_analytics(_all_reports(subject))
