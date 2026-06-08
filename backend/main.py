"""
MechAssess FastAPI Backend
RVCE Mechanical Engineering AI Assessment Platform
"""

import json
import sys
import os
import uuid
import random
import threading
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Import LangGraph pipeline ─────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from evaluation.drawing_evaluator import evaluate_drawing
    DRAWING_EVAL_AVAILABLE = True
except ImportError:
    DRAWING_EVAL_AVAILABLE = False

try:
    from generation.langgraph_pipeline import (
        run_pipeline,
        get_all_questions as _db_get_questions,
        delete_question as _db_delete_question,
        LANGGRAPH_AVAILABLE,
        OLLAMA_AVAILABLE,
    )
    HAS_PIPELINE = True
except Exception as _import_err:
    HAS_PIPELINE = False
    LANGGRAPH_AVAILABLE = False
    OLLAMA_AVAILABLE = False

app = FastAPI(title="MechAssess API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class QuestionGenerateRequest(BaseModel):
    subject: str
    unit: str
    bloom_level: int
    question_type: str
    co: str
    count: int = 4
    marks: int = 10

class OverrideRequest(BaseModel):
    score: float
    reason: str

class ExamCreateRequest(BaseModel):
    title: str
    subject: str
    total_marks: int
    duration: int
    question_ids: List[str]

# ── Mock data stores ──────────────────────────────────────────────────────────

MOCK_STUDENTS = [
    {"id": "ST-001", "usn": "1RV23ME001", "name": "Arjun Sharma", "section": "ME-A"},
    {"id": "ST-002", "usn": "1RV23ME002", "name": "Priya Nair", "section": "ME-A"},
    {"id": "ST-003", "usn": "1RV23ME003", "name": "Rohan Das", "section": "ME-A"},
    {"id": "ST-004", "usn": "1RV23ME004", "name": "Kavitha Rao", "section": "ME-B"},
    {"id": "ST-005", "usn": "1RV23ME005", "name": "Suresh M", "section": "ME-B"},
    {"id": "ST-006", "usn": "1RV23ME006", "name": "Deepa Krishnan", "section": "ME-B"},
    {"id": "ST-007", "usn": "1RV23ME007", "name": "Arun Bhat", "section": "ME-C"},
    {"id": "ST-008", "usn": "1RV23ME008", "name": "Ravi Kumar", "section": "ME-C"},
]

MOCK_SUBMISSIONS = [
    {
        "id": "S-031", "studentId": "ST-001", "questionId": "Q-001",
        "type": "theory",
        "content": "The zeroth law states that if two systems are in thermal equilibrium with a third, they are in thermal equilibrium with each other.",
        "submittedAt": "2026-05-10T09:15:00Z", "status": "graded",
    },
    {
        "id": "S-032", "studentId": "ST-002", "questionId": "Q-002",
        "type": "theory",
        "content": "For isothermal process, T = constant. Work done W = nRT ln(V2/V1).",
        "submittedAt": "2026-05-10T09:18:00Z", "status": "graded",
    },
    {
        "id": "S-033", "studentId": "ST-003", "questionId": "Q-003",
        "type": "numerical",
        "content": "eta = 1 - T2/T1 = 1 - 400/800 = 0.5. Heat supplied = W/eta = 150/0.5 = 300 kW. Heat rejected = 300 - 150 = 150 kW.",
        "submittedAt": "2026-05-10T09:20:00Z", "status": "pending",
    },
    {
        "id": "S-034", "studentId": "ST-004", "questionId": "Q-003",
        "type": "numerical",
        "content": "eta = 1 - 300/900 = 0.667. Heat supplied = 150/0.667 = 224.8 kW.",
        "submittedAt": "2026-05-10T09:25:00Z", "status": "pending",
    },
]

MOCK_EXAMS = [
    {
        "id": "EX-001", "title": "Thermodynamics Mid-Semester Examination",
        "subject": "Thermodynamics", "totalMarks": 50, "duration": 90,
        "questions": ["Q-001", "Q-002", "Q-003", "Q-008"],
        "createdAt": "2026-05-08T10:00:00Z", "status": "published",
    },
    {
        "id": "EX-002", "title": "Fluid Mechanics Unit Test — Unit 2 & 3",
        "subject": "Fluid Mechanics", "totalMarks": 30, "duration": 60,
        "questions": ["Q-005", "Q-006"],
        "createdAt": "2026-05-09T10:00:00Z", "status": "draft",
    },
    {
        "id": "EX-003", "title": "Strength of Materials — Bending & Torsion",
        "subject": "Strength of Materials", "totalMarks": 40, "duration": 90,
        "questions": ["Q-004"],
        "createdAt": "2026-05-10T10:00:00Z", "status": "draft",
    },
]

GRADE_RESULTS = {}

# ── SSE agent sequence ────────────────────────────────────────────────────────

SSE_AGENTS = [
    "BloomAnalyzer",
    "Scout",
    "Generator",
    "QualityValidator",
    "DifficultyValidator",
    "CorrectnessValidator",
    "PedagogyTagger",
    "SyllabusGuardian",
    "Archivist",
]

# ── Helper ────────────────────────────────────────────────────────────────────

def _normalize_question(q: dict) -> dict:
    """Convert DB snake_case keys to camelCase for frontend."""
    return {
        "id": q.get("id"),
        "text": q.get("text"),
        "type": q.get("type"),
        "subject": q.get("subject"),
        "unit": q.get("unit"),
        "bloomLevel": q.get("bloom_level"),
        "bloomLabel": q.get("bloom_label"),
        "co": q.get("co"),
        "po": q.get("po"),
        "marks": q.get("marks"),
        "difficulty": q.get("difficulty"),
        "createdAt": q.get("created_at", datetime.utcnow().isoformat() + "Z"),
    }

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "langgraph_available": LANGGRAPH_AVAILABLE,
        "ollama_available": OLLAMA_AVAILABLE,
        "pipeline_available": HAS_PIPELINE,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/stats")
async def get_stats():
    total_questions = 0
    if HAS_PIPELINE:
        try:
            total_questions = len(_db_get_questions())
        except Exception:
            total_questions = 0

    return {
        "totalQuestions": total_questions,
        "activeExams": sum(1 for e in MOCK_EXAMS if e["status"] == "published"),
        "submissionsPending": sum(1 for s in MOCK_SUBMISSIONS if s["status"] == "pending"),
        "avgCOAttainment": 76.8,
        "timeSavedHours": 186,
        "questionsThisMonth": 48,
        "totalStudents": len(MOCK_STUDENTS),
        "gradedToday": 34,
    }


@app.post("/api/questions/generate")
async def generate_questions(req: QuestionGenerateRequest):
    if not HAS_PIPELINE:
        raise HTTPException(status_code=503, detail="Generation pipeline not available")

    try:
        questions = run_pipeline(
            subject=req.subject,
            unit=req.unit,
            bloom_level=req.bloom_level,
            question_type=req.question_type,
            co=req.co,
            count=req.count,
        )
        normalized = [_normalize_question(q) for q in questions]
        source = "langgraph_pipeline" if (LANGGRAPH_AVAILABLE and OLLAMA_AVAILABLE) else "pipeline_mock_fallback"
        return {"questions": normalized, "source": source}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@app.get("/api/questions/generate/stream")
async def stream_generate_questions(
    subject: str,
    unit: str,
    bloom_level: int = 3,
    question_type: str = "theory",
    co: str = "CO1",
    count: int = 4,
):
    """
    SSE endpoint that streams agent progress events during question generation.
    Yields JSON lines:
      data: {"agent": "BloomAnalyzer", "status": "running"}
      data: {"agent": "BloomAnalyzer", "status": "done"}
      ...
      data: {"done": true, "questions": [...]}
    """

    def event_generator():
        result_holder: dict = {"questions": [], "error": None}
        thread_started = [False]

        def run_generation():
            try:
                qs = run_pipeline(
                    subject=subject,
                    unit=unit,
                    bloom_level=bloom_level,
                    question_type=question_type,
                    co=co,
                    count=count,
                )
                result_holder["questions"] = qs
            except Exception as ex:
                result_holder["error"] = str(ex)

        gen_thread = threading.Thread(target=run_generation, daemon=True)
        agent_delay = 0.6  # pacing per agent

        for agent_name in SSE_AGENTS:
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'running'})}\n\n"
            time.sleep(agent_delay * 0.4)

            # Kick off real generation at the Generator step
            if agent_name == "Generator" and not thread_started[0]:
                gen_thread.start()
                thread_started[0] = True

            yield f"data: {json.dumps({'agent': agent_name, 'status': 'done'})}\n\n"
            time.sleep(agent_delay * 0.6)

        # Ensure thread is started even if something skipped Generator step
        if not thread_started[0]:
            gen_thread.start()

        gen_thread.join(timeout=120)

        normalized = [_normalize_question(q) for q in result_holder["questions"]]
        yield f"data: {json.dumps({'done': True, 'questions': normalized, 'error': result_holder.get('error')})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/questions")
async def get_questions(
    subject: Optional[str] = None,
    type: Optional[str] = None,
    bloom_level: Optional[int] = None,
    co: Optional[str] = None,
    unit: Optional[str] = None,
):
    if HAS_PIPELINE:
        try:
            questions = _db_get_questions(
                subject=subject,
                unit=unit,
                bloom_level=bloom_level,
                q_type=type,
            )
            normalized = []
            for q in questions:
                if co and q.get("co") != co:
                    continue
                normalized.append(_normalize_question(q))
            return {"questions": normalized, "total": len(normalized)}
        except Exception:
            pass

    return {"questions": [], "total": 0}


@app.delete("/api/questions/{question_id}")
async def delete_question_route(question_id: str):
    if HAS_PIPELINE:
        try:
            _db_delete_question(question_id)
            return {"success": True, "id": question_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="Question not found")


@app.get("/api/students")
async def get_students():
    return {"students": MOCK_STUDENTS, "total": len(MOCK_STUDENTS)}


@app.get("/api/submissions")
async def get_submissions():
    return {"submissions": MOCK_SUBMISSIONS, "total": len(MOCK_SUBMISSIONS)}


@app.post("/api/submissions/{submission_id}/grade")
async def grade_submission(submission_id: str):
    sub = next((s for s in MOCK_SUBMISSIONS if s["id"] == submission_id), None)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    ai_score = round(random.uniform(4.0, 9.5), 1)
    confidence = round(random.uniform(0.68, 0.97), 2)
    result = {
        "submissionId": submission_id,
        "aiScore": ai_score,
        "maxScore": 10,
        "confidence": confidence,
        "feedback": (
            "Answer demonstrates good conceptual understanding. "
            "Some key derivations require elaboration. "
            "Terminology usage is appropriate for the subject domain."
        ),
        "co": "CO1",
        "po": "PO1",
        "isOverridden": False,
        "gradedAt": datetime.utcnow().isoformat() + "Z",
    }
    GRADE_RESULTS[submission_id] = result
    return result


@app.post("/api/submissions/{submission_id}/override")
async def override_grade(submission_id: str, body: OverrideRequest):
    sub = next((s for s in MOCK_SUBMISSIONS if s["id"] == submission_id), None)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    existing = GRADE_RESULTS.get(submission_id, {"aiScore": 7.0, "maxScore": 10})
    result = {
        **existing,
        "submissionId": submission_id,
        "isOverridden": True,
        "overriddenScore": body.score,
        "overrideReason": body.reason,
        "overriddenBy": "faculty",
        "overriddenAt": datetime.utcnow().isoformat() + "Z",
    }
    GRADE_RESULTS[submission_id] = result
    return result


@app.get("/api/analytics/co")
async def get_co_analytics():
    co_data = [
        {
            "co": "CO1",
            "description": "Apply laws of thermodynamics to analyze engineering systems",
            "averageAttainment": 78.2,
            "studentsAchieved": 48,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 12, "L2": 18, "L3": 20, "L4": 15, "L5": 8, "L6": 3},
        },
        {
            "co": "CO2",
            "description": "Analyze power cycles and refrigeration systems",
            "averageAttainment": 65.1,
            "studentsAchieved": 40,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 8, "L2": 14, "L3": 22, "L4": 18, "L5": 10, "L6": 4},
        },
        {
            "co": "CO3",
            "description": "Solve problems in strength of materials and structural analysis",
            "averageAttainment": 82.4,
            "studentsAchieved": 51,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 10, "L2": 15, "L3": 25, "L4": 20, "L5": 12, "L6": 5},
        },
        {
            "co": "CO4",
            "description": "Apply fluid mechanics principles to flow analysis",
            "averageAttainment": 71.3,
            "studentsAchieved": 44,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 9, "L2": 16, "L3": 21, "L4": 17, "L5": 9, "L6": 2},
        },
        {
            "co": "CO5",
            "description": "Interpret and produce engineering drawings per IS standards",
            "averageAttainment": 88.0,
            "studentsAchieved": 55,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 6, "L2": 12, "L3": 28, "L4": 14, "L5": 7, "L6": 3},
        },
    ]
    return {"co_analytics": co_data, "overall_attainment": 77.0, "target": 70}


@app.get("/api/exams")
async def get_exams():
    return {"exams": MOCK_EXAMS, "total": len(MOCK_EXAMS)}


@app.post("/api/exams")
async def create_exam(body: ExamCreateRequest):
    exam = {
        "id": f"EX-{str(uuid.uuid4())[:6].upper()}",
        "title": body.title,
        "subject": body.subject,
        "totalMarks": body.total_marks,
        "duration": body.duration,
        "questions": body.question_ids,
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "status": "draft",
    }
    MOCK_EXAMS.append(exam)
    return exam


@app.post("/api/eval/drawing")
async def eval_drawing(
    file: UploadFile = File(None),
    max_marks: int = Form(20),
    student_usn: str = Form(""),
    assignment: str = Form(""),
):
    image_path = None
    if file and file.filename:
        upload_dir = Path(__file__).parent.parent / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        image_path = str(upload_dir / file.filename)
        with open(image_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    if DRAWING_EVAL_AVAILABLE:
        result = evaluate_drawing(image_path, max_marks)
    else:
        result = {
            "ai_score": 14.0, "max_score": max_marks, "confidence": 0.6,
            "detected_elements": [], "violations": [],
            "violation_deductions": 0, "vlm_output": {},
            "preprocessing_applied": False,
            "feedback": "Drawing evaluator module not available.",
        }
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
