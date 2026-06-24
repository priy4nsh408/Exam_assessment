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
    from evaluation.theory_evaluator import evaluate_theory
    THEORY_EVAL_AVAILABLE = True
except ImportError:
    THEORY_EVAL_AVAILABLE = False

try:
    from evaluation.numerical_grader import grade_numerical
    NUMERICAL_EVAL_AVAILABLE = True
except ImportError:
    NUMERICAL_EVAL_AVAILABLE = False

try:
    from generation.langgraph_pipeline import (
        run_pipeline,
        run_pipeline_for_specs as _db_run_pipeline_for_specs,
        get_all_questions as _db_get_questions,
        get_question_by_id as _db_get_question_by_id,
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

class TheoryEvalRequest(BaseModel):
    question_id: str
    student_answer: str

class QuestionSpecRequest(BaseModel):
    bloom_level: int
    co: str
    marks: int

class PipelineGenerateRequest(BaseModel):
    """
    Step 1: faculty chooses subject + chapter (unit) + question_type once
    for the batch, and Bloom level / CO / marks individually for EACH
    question via `questions` (one spec per question - its length is the
    number of questions to generate).
    """
    subject: str
    chapter: str
    question_type: str = "theory"
    questions: List[QuestionSpecRequest]

class PipelineAssessRequest(BaseModel):
    """Step 3: grade a student's answer against a real generated question.
    Works for theory and numerical question types (drawing needs an image
    file, so it stays on the dedicated /api/eval/drawing endpoint)."""
    question_id: str
    student_answer: str

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
        "answerKey": q.get("answer_key"),
        "sourceChunk": q.get("source_chunk"),
        "generationExplanation": q.get("generation_explanation"),
        "answerKeyExplanation": q.get("answer_key_explanation"),
        "createdAt": q.get("created_at", datetime.utcnow().isoformat() + "Z"),
    }

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "MechAssess API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "note": "Open http://localhost:5173 in your browser for the dashboard UI."
    }

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


@app.post("/api/pipeline/generate")
async def pipeline_generate(req: PipelineGenerateRequest):
    """
    Full Step 1+2 pipeline: generates one question per entry in
    `req.questions` (each with its own Bloom level/CO/marks), then for each
    question writes a raw-data-grounded answer key plus two explanations:
      - generationExplanation: why/where the question was generated from
      - answerKeyExplanation: why the answer key is correct + its source
    """
    if not HAS_PIPELINE:
        raise HTTPException(status_code=503, detail="Generation pipeline not available")
    if not req.questions:
        raise HTTPException(status_code=400, detail="At least one question spec is required")

    try:
        specs = [q.dict() for q in req.questions]
        questions = _db_run_pipeline_for_specs(
            subject=req.subject, unit=req.chapter,
            question_type=req.question_type, specs=specs,
        )
        normalized = [_normalize_question(q) for q in questions]
        source = "langgraph_pipeline" if (LANGGRAPH_AVAILABLE and OLLAMA_AVAILABLE) else "pipeline_mock_fallback"
        shortfall = len(req.questions) - len(normalized)
        response = {"questions": normalized, "source": source, "requested": len(req.questions)}
        if shortfall > 0:
            response["warning"] = (
                f"{shortfall} question(s) could not be generated for their requested "
                f"Bloom level/CO combination (e.g. due to deduplication or sparse source data)."
            )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@app.post("/api/pipeline/assess")
async def pipeline_assess(req: PipelineAssessRequest):
    """
    Step 3: grade a student's answer against a real generated question,
    using that question's raw-data-derived answer key as the reference.
    Returns the score plus an explicit explanation of where marks were
    awarded and why any marks were deducted.
    """
    if not HAS_PIPELINE:
        raise HTTPException(status_code=503, detail="Pipeline not available")

    question = _db_get_question_by_id(req.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    reference_answer = question.get("answer_key") or question.get("source_chunk") or ""
    q_type = question.get("type", "theory")

    if q_type == "numerical":
        if not NUMERICAL_EVAL_AVAILABLE:
            raise HTTPException(status_code=503, detail="Numerical evaluator not available")
        result = grade_numerical(
            question=question["text"], student_solution=req.student_answer,
            reference_answer=reference_answer, subject=question["subject"], max_marks=question["marks"],
        )
    elif q_type == "theory":
        if not THEORY_EVAL_AVAILABLE:
            raise HTTPException(status_code=503, detail="Theory evaluator not available")
        result = evaluate_theory(
            question=question["text"], student_answer=req.student_answer,
            reference_answer=reference_answer, subject=question["subject"], max_marks=question["marks"],
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Drawing questions require an image upload - use POST /api/eval/drawing with question_id instead.",
        )

    return {
        "questionId": req.question_id,
        "questionText": question["text"],
        "answerKey": question.get("answer_key"),
        "answerKeyExplanation": question.get("answer_key_explanation"),
        "aiScore": result["ai_score"],
        "maxScore": result["max_score"],
        "explanation": result.get("explanation", result.get("feedback")),
        "feedback": result.get("feedback"),
        "details": result,
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


@app.get("/api/questions/{question_id}")
async def get_question(question_id: str):
    if not HAS_PIPELINE:
        raise HTTPException(status_code=503, detail="Pipeline not available")
    question = _db_get_question_by_id(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return _normalize_question(question)


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

    sub_type = sub.get("type")
    question = _db_get_question_by_id(sub["questionId"]) if HAS_PIPELINE else None
    reference_answer = (question.get("answer_key") or question.get("source_chunk") or "") if question else ""
    question_text = question["text"] if question else sub["questionId"]
    subject = question["subject"] if question else ""
    max_marks = question["marks"] if question else 10
    co, po = (question["co"], question["po"]) if question else ("CO1", "PO1")

    if sub_type == "theory" and THEORY_EVAL_AVAILABLE:
        eval_result = evaluate_theory(
            question=question_text, student_answer=sub["content"],
            reference_answer=reference_answer, subject=subject, max_marks=max_marks,
        )
        result = {
            "submissionId": submission_id,
            "aiScore": eval_result["ai_score"], "maxScore": eval_result["max_score"],
            "confidence": eval_result["confidence"], "feedback": eval_result["feedback"],
            "keywordScore": eval_result["keyword_score"], "semanticScore": eval_result["semantic_score"],
            "matchedKeywords": eval_result["keywords"]["found"], "missingKeywords": eval_result["keywords"]["missing"],
            "co": co, "po": po, "isOverridden": False,
            "gradedAt": datetime.utcnow().isoformat() + "Z",
        }

    elif sub_type == "numerical" and NUMERICAL_EVAL_AVAILABLE:
        eval_result = grade_numerical(
            question=question_text, student_solution=sub["content"],
            reference_answer=reference_answer, subject=subject, max_marks=max_marks,
        )
        result = {
            "submissionId": submission_id,
            "aiScore": eval_result["ai_score"], "maxScore": eval_result["max_score"],
            "confidence": eval_result.get("confidence", 0.6), "feedback": eval_result["feedback"],
            "baseScore": eval_result["base_score"], "deductions": eval_result["deductions"],
            "formulaMentioned": eval_result["formula_mentioned"],
            "finalAnswerCorrect": eval_result["final_answer_correct"],
            "steps": eval_result.get("steps", []),
            "co": co, "po": po, "isOverridden": False,
            "gradedAt": datetime.utcnow().isoformat() + "Z",
        }

    else:
        # Drawing submissions carry an image file, not text content, so they're
        # graded through the dedicated multipart /api/eval/drawing endpoint instead.
        result = {
            "submissionId": submission_id,
            "aiScore": None, "maxScore": max_marks, "confidence": 0.0,
            "feedback": "This submission type is graded via its dedicated evaluator endpoint "
                        "(/api/eval/drawing for diagrams).",
            "co": co, "po": po, "isOverridden": False,
            "gradedAt": datetime.utcnow().isoformat() + "Z",
        }

    if not question and sub_type in ("theory", "numerical"):
        result["feedback"] += (
            " (No matching generated question with source data was found "
            "for this submission, so grading used a reduced reference.)"
        )

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


@app.post("/api/eval/theory")
async def eval_theory(body: TheoryEvalRequest):
    if not (THEORY_EVAL_AVAILABLE and HAS_PIPELINE):
        raise HTTPException(status_code=503, detail="Theory evaluator not available")

    question = _db_get_question_by_id(body.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    reference_answer = question.get("answer_key") or question.get("source_chunk") or ""
    eval_result = evaluate_theory(
        question=question["text"],
        student_answer=body.student_answer,
        reference_answer=reference_answer,
        subject=question["subject"],
        max_marks=question["marks"],
    )
    return {
        "questionId": body.question_id,
        "aiScore": eval_result["ai_score"],
        "maxScore": eval_result["max_score"],
        "confidence": eval_result["confidence"],
        "feedback": eval_result["feedback"],
        "keywordScore": eval_result["keyword_score"],
        "semanticScore": eval_result["semantic_score"],
        "matchedKeywords": eval_result["keywords"]["found"],
        "missingKeywords": eval_result["keywords"]["missing"],
        "hadReferenceData": bool(reference_answer),
    }


@app.post("/api/eval/drawing")
async def eval_drawing(
    file: UploadFile = File(None),
    max_marks: int = Form(20),
    student_usn: str = Form(""),
    assignment: str = Form(""),
    question_id: str = Form(""),
    expected_parts: str = Form(""),       # comma-separated, optional override
    expected_dimensions: str = Form(""),  # comma-separated, optional override
):
    image_path = None
    if file and file.filename:
        upload_dir = Path(__file__).parent.parent / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        image_path = str(upload_dir / file.filename)
        with open(image_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    question_text = assignment
    if question_id and HAS_PIPELINE:
        question = _db_get_question_by_id(question_id)
        if question:
            question_text = question["text"]
            max_marks = question["marks"]

    parts_override = [p.strip() for p in expected_parts.split(",") if p.strip()] or None
    dims_override = [d.strip() for d in expected_dimensions.split(",") if d.strip()] or None

    if DRAWING_EVAL_AVAILABLE:
        result = evaluate_drawing(
            image_path, max_marks,
            question=question_text,
            expected_parts=parts_override,
            expected_dimensions=dims_override,
        )
    else:
        result = {
            "ai_score": 14.0, "max_score": max_marks, "confidence": 0.6,
            "detected_elements": [], "violations": [],
            "violation_deductions": 0, "vlm_output": {},
            "preprocessing_applied": False,
            "feedback": "Drawing evaluator module not available.",
        }
    return result


@app.post("/api/eval/numerical")
async def eval_numerical(
    question_id: str = Form(""),
    question_text: str = Form(""),
    student_solution: str = Form(...),
    max_marks: int = Form(10),
    expected_formula: str = Form(""),
    expected_final_answer: str = Form(""),
):
    if not NUMERICAL_EVAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Numerical evaluator not available")

    reference_answer = ""
    subject = ""
    if question_id and HAS_PIPELINE:
        question = _db_get_question_by_id(question_id)
        if question:
            reference_answer = question.get("answer_key") or question.get("source_chunk") or ""
            question_text = question_text or question["text"]
            subject = question["subject"]
            max_marks = question["marks"]

    result = grade_numerical(
        question=question_text,
        student_solution=student_solution,
        reference_answer=reference_answer,
        expected_formula=expected_formula,
        expected_final_answer=expected_final_answer,
        subject=subject,
        max_marks=max_marks,
    )
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
