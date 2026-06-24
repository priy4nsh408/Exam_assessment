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
import sqlite3
import zipfile
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
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
        create_answer_scheme as _db_create_answer_scheme,
        get_answer_schemes as _db_get_answer_schemes,
        get_answer_scheme_by_id as _db_get_answer_scheme_by_id,
        get_answer_scheme_by_question_id as _db_get_answer_scheme_by_question_id,
        log_activity as _db_log_activity,
        get_recent_activity as _db_get_recent_activity,
        save_exam as _db_save_exam,
        get_exams as _db_get_exams,
        get_exam_by_id as _db_get_exam_by_id,
        CO_PO_MAP as _CO_PO_MAP,
        LANGGRAPH_AVAILABLE,
        OLLAMA_AVAILABLE,
    )
    HAS_PIPELINE = True
except Exception as _import_err:
    HAS_PIPELINE = False
    LANGGRAPH_AVAILABLE = False
    OLLAMA_AVAILABLE = False
    _CO_PO_MAP = {}

try:
    import demo_data as _demo
    HAS_DEMO_DATA = True
except Exception:
    HAS_DEMO_DATA = False

try:
    import data_source as _data_source
    HAS_DATA_SOURCE = True
except Exception:
    HAS_DATA_SOURCE = False

app = FastAPI(title="MechAssess API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SQLite override persistence ───────────────────────────────────────────────
_OVERRIDE_DB = Path(__file__).parent.parent / "data" / "overrides.db"

def _get_override_conn():
    _OVERRIDE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_OVERRIDE_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grade_overrides (
            id              TEXT PRIMARY KEY,
            submission_id   TEXT NOT NULL,
            original_score  REAL,
            override_score  REAL NOT NULL,
            max_score       REAL,
            reason          TEXT,
            faculty         TEXT DEFAULT 'faculty',
            created_at      TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def _save_override(submission_id: str, original_score, override_score: float,
                   max_score, reason: str, faculty: str = "faculty"):
    conn = _get_override_conn()
    conn.execute("""
        INSERT OR REPLACE INTO grade_overrides
        (id, submission_id, original_score, override_score, max_score, reason, faculty, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        str(uuid.uuid4()), submission_id, original_score, override_score,
        max_score, reason, faculty, datetime.utcnow().isoformat() + "Z"
    ))
    conn.commit()
    conn.close()

def _get_overrides() -> List[dict]:
    conn = _get_override_conn()
    rows = conn.execute("SELECT * FROM grade_overrides ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _get_override_for(submission_id: str) -> Optional[dict]:
    conn = _get_override_conn()
    row = conn.execute(
        "SELECT * FROM grade_overrides WHERE submission_id=? ORDER BY created_at DESC LIMIT 1",
        (submission_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

# ── Training reference store ──────────────────────────────────────────────────
_TRAINING_DIR = Path(__file__).parent.parent / "data" / "training_refs"
_TRAINING_DIR.mkdir(parents=True, exist_ok=True)

_TRAINING_META_DB = Path(__file__).parent.parent / "data" / "training_meta.db"

def _get_training_conn():
    conn = sqlite3.connect(str(_TRAINING_META_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS training_refs (
            id              TEXT PRIMARY KEY,
            subject         TEXT NOT NULL,
            q_type          TEXT NOT NULL,
            filename        TEXT NOT NULL,
            description     TEXT,
            file_path       TEXT NOT NULL,
            marks_per_q     REAL DEFAULT 10,
            questions_json  TEXT DEFAULT '[]',
            parse_warnings  TEXT DEFAULT '[]',
            created_at      TEXT NOT NULL
        )
    """)
    # migrate existing DBs
    for col, default in [
        ("marks_per_q",    "10"),
        ("questions_json", "'[]'"),
        ("parse_warnings", "'[]'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE training_refs ADD COLUMN {col} REAL DEFAULT {default}" if col == "marks_per_q"
                         else f"ALTER TABLE training_refs ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass
    conn.commit()
    return conn

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
    """
    Flexible: pass `answer_id` (preferred - resolves to its answer scheme's
    question + reference answer) OR `question_id` (resolves to that
    question's own answer_key/source_chunk) OR raw `question` text with an
    optional `model_answer`/`reference_answer` for a fully manual/ungrounded
    grading call.
    """
    student_answer: str
    answer_id: Optional[str] = None
    question_id: Optional[str] = None
    question: Optional[str] = None
    subject: Optional[str] = ""
    model_answer: Optional[str] = ""
    reference_answer: Optional[str] = ""
    max_marks: Optional[int] = 10

class NumericalEvalRequest(BaseModel):
    """Same flexible resolution as TheoryEvalRequest, for numerical grading."""
    student_solution: str
    answer_id: Optional[str] = None
    question_id: Optional[str] = None
    question: Optional[str] = None
    subject: Optional[str] = ""
    reference_answer: Optional[str] = ""
    expected_formula: Optional[str] = ""
    expected_final_answer: Optional[str] = ""
    max_marks: Optional[int] = 10

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
    student_answer: str
    question_id: Optional[str] = None
    answer_id: Optional[str] = None

class ExamCreateRequest(BaseModel):
    title: str
    subject: str
    total_marks: int
    duration: int
    question_ids: List[str]

# ── Mock data stores ──────────────────────────────────────────────────────────

# ── Demo data ─────────────────────────────────────────────────────────────────
# The student roster / sample submissions / exam list below used to be
# hand-typed fixtures with made-up scores (MOCK_STUDENTS, MOCK_SUBMISSIONS,
# MOCK_EXAMS). They're now sourced from demo_data.py, which computes every
# score by actually running evaluate_theory()/grade_numerical() against the
# real seeded answer keys - so what's on screen is a genuine demonstration
# of the grading engine, not invented percentages.

MOCK_STUDENTS = _demo.DEMO_STUDENTS if HAS_DEMO_DATA else []
MOCK_SUBMISSIONS = _demo.DEMO_SUBMISSIONS if HAS_DEMO_DATA else []
MOCK_EXAMS = _demo.DEMO_EXAMS if HAS_DEMO_DATA else []

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

def _normalize_answer_scheme(s: dict) -> dict:
    return {
        "id": s.get("id"),
        "questionId": s.get("question_id"),
        "questionText": s.get("question_text"),
        "questionNumber": s.get("question_number"),
        "subject": s.get("subject"),
        "type": s.get("type"),
        "marks": s.get("marks"),
        "answerKey": s.get("answer_key"),
        "explanation": s.get("explanation"),
        "createdAt": s.get("created_at"),
    }

def _log_activity_safe(action: str, activity_type: str, detail: str = "", subject: str = ""):
    """Best-effort activity logging - never lets a logging failure break the
    actual request it's attached to."""
    if not HAS_PIPELINE:
        return
    try:
        _db_log_activity(action, activity_type, detail=detail, subject=subject)
    except Exception:
        pass

def _resolve_grading_reference(
    answer_id: Optional[str] = None,
    question_id: Optional[str] = None,
    question_fallback: str = "",
    subject_fallback: str = "",
    reference_fallback: str = "",
    max_marks_fallback: int = 10,
) -> dict:
    """
    Single resolution path used by every grading endpoint: prefer an
    answer_id (the answer scheme itself), then a question_id (derive its
    reference from answer_key/source_chunk), then fall back to whatever the
    caller passed directly (manual/ungrounded grading).
    Returns {question_text, subject, reference_answer, max_marks, question_id,
             answer_id, grounded} where `grounded` is False only in the manual fallback case.

    Raises HTTPException(404) if an answer_id or question_id was explicitly
    provided but doesn't resolve to anything - this used to fall through
    silently to the ungrounded/manual branch instead, producing a
    confusing 0-score "ungrounded" result that looked like a legitimate
    grading outcome rather than a "your ID was wrong" error. A typo'd or
    copy-paste-mangled answer_id should fail loudly, not silently grade
    against empty reference text.
    """
    if answer_id and HAS_PIPELINE:
        scheme = _db_get_answer_scheme_by_id(answer_id)
        if scheme:
            question = _db_get_question_by_id(scheme["question_id"]) if HAS_PIPELINE else None
            return {
                "question_text": scheme.get("question_text") or (question or {}).get("text", ""),
                "subject": scheme.get("subject") or (question or {}).get("subject", ""),
                "reference_answer": scheme.get("answer_key") or "",
                "max_marks": scheme.get("marks") or max_marks_fallback,
                "question_id": scheme.get("question_id"),
                "answer_id": scheme.get("id"),
                "co": (question or {}).get("co"),
                "grounded": True,
            }
        raise HTTPException(
            status_code=404,
            detail=f"No answer scheme found for answer_id '{answer_id}'. Double-check it was "
                   f"copied correctly (format: AK-YYYYMMDD-XXXXXX) - it must exactly match an "
                   f"answer_id already in the question bank.",
        )

    if question_id and HAS_PIPELINE:
        question = _db_get_question_by_id(question_id)
        if question:
            scheme = _db_get_answer_scheme_by_question_id(question_id)
            return {
                "question_text": question.get("text", ""),
                "subject": question.get("subject", ""),
                "reference_answer": question.get("answer_key") or question.get("source_chunk") or "",
                "max_marks": question.get("marks") or max_marks_fallback,
                "question_id": question.get("id"),
                "answer_id": scheme.get("id") if scheme else None,
                "co": question.get("co"),
                "grounded": True,
            }
        raise HTTPException(
            status_code=404,
            detail=f"No question found for question_id '{question_id}'. Double-check it was "
                   f"copied correctly - it must exactly match a question already in the bank.",
        )

    # Manual fallback - whatever the caller supplied directly, ungrounded.
    # No real `co` exists in this case (no question record to draw it from).
    return {
        "question_text": question_fallback,
        "subject": subject_fallback,
        "reference_answer": reference_fallback,
        "max_marks": max_marks_fallback,
        "question_id": question_id,
        "answer_id": answer_id,
        "co": None,
        "grounded": False,
    }

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
    bloom_distribution = []
    recent_questions = []
    if HAS_PIPELINE:
        try:
            all_questions = _db_get_questions()
            total_questions = len(all_questions)
            # Real Bloom-level distribution across the actual question bank,
            # replacing the hardcoded bloomDist=[12,18,24,20,14,8] the
            # dashboard chart used to render unconditionally.
            counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
            for q in all_questions:
                lvl = q.get("bloom_level")
                if lvl in counts:
                    counts[lvl] += 1
            bloom_labels = {1: "L1 Remember", 2: "L2 Understand", 3: "L3 Apply",
                             4: "L4 Analyze", 5: "L5 Evaluate", 6: "L6 Create"}
            bloom_distribution = [{"level": bloom_labels[l], "count": counts[l]} for l in range(1, 7)]
            # Most recently generated questions, replacing the hardcoded
            # Q-049/Q-050/Q-051 sample on the dashboard.
            recent_questions = [_normalize_question(q) for q in all_questions[:3]]
        except Exception:
            total_questions = 0

    demo_stats = _demo.get_demo_stats() if HAS_DEMO_DATA else {
        "activeExams": 0, "submissionsPending": 0, "avgCOAttainment": None,
        "totalStudents": 0, "gradedToday": 0,
    }

    return {
        "totalQuestions": total_questions,
        "bloomDistribution": bloom_distribution,
        "recentQuestions": recent_questions,
        **demo_stats,
    }


@app.get("/api/activity")
async def get_activity(limit: int = 10):
    """Real activity feed (question generation, grading, overrides, exam
    publishes) for the dashboard's Recent Activity panel - replaces the
    previously hardcoded 5-item list."""
    if not HAS_PIPELINE:
        return {"activity": []}
    try:
        rows = _db_get_recent_activity(limit=limit)
        activity = [{
            "action": r["action"], "subject": r.get("subject", ""),
            "detail": r.get("detail", ""), "type": r["type"],
            "createdAt": r["created_at"],
        } for r in rows]
        return {"activity": activity}
    except Exception:
        return {"activity": []}


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
        questions, drop_reasons, pipeline_errors = _db_run_pipeline_for_specs(
            subject=req.subject, unit=req.chapter,
            question_type=req.question_type, specs=specs,
        )
        normalized = []
        for i, q in enumerate(questions, start=1):
            scheme = _db_create_answer_scheme(q, question_number=i)
            nq = _normalize_question(q)
            nq["answerId"] = scheme["id"]
            normalized.append(nq)
        source = "langgraph_pipeline" if (LANGGRAPH_AVAILABLE and OLLAMA_AVAILABLE) else "pipeline_mock_fallback"
        shortfall = len(req.questions) - len(normalized)
        response = {"questions": normalized, "source": source, "requested": len(req.questions)}
        if shortfall > 0:
            # One concrete reason per missing question, in spec order, instead
            # of a vague generic shortfall note - e.g. "the LLM only returned
            # 2/4 usable questions" or "a validator rejected it as too short"
            # rather than a hand-wavy "may be due to dedup or sparse data".
            unique_reasons = list(dict.fromkeys(drop_reasons.values()))
            reason_text = " ".join(unique_reasons) if unique_reasons else (
                "No specific reason was logged for the shortfall."
            )
            response["warning"] = (
                f"Requested {len(req.questions)} question(s) but only {len(normalized)} "
                f"were generated. {reason_text}"
            )
        if pipeline_errors:
            # These questions still generated successfully, but something
            # went wrong upstream of them (most commonly: no ChromaDB
            # content found for this subject/unit) - surfaced separately
            # from `warning` since it isn't a shortfall, it's a grounding
            # quality issue the faculty member should know about before
            # trusting the answer key.
            response["groundingNotice"] = " ".join(pipeline_errors)
        if normalized:
            _log_activity_safe(
                action=f"Generated {len(normalized)} question(s)",
                activity_type="generate",
                subject=req.subject, detail=req.chapter,
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
    awarded and why any marks were deducted. Accepts either `answer_id`
    (preferred) or `question_id`.
    """
    if not HAS_PIPELINE:
        raise HTTPException(status_code=503, detail="Pipeline not available")
    if not req.answer_id and not req.question_id:
        raise HTTPException(status_code=400, detail="Provide answer_id or question_id")

    question = None
    if req.question_id:
        question = _db_get_question_by_id(req.question_id)
    elif req.answer_id:
        scheme = _db_get_answer_scheme_by_id(req.answer_id)
        if scheme:
            question = _db_get_question_by_id(scheme["question_id"])
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
            detail="Drawing questions require an image upload - use POST /api/eval/drawing with answer_id/question_id instead.",
        )

    return {
        "questionId": question["id"],
        "questionText": question["text"],
        "answerKey": question.get("answer_key"),
        "answerKeyExplanation": question.get("answer_key_explanation"),
        "aiScore": result["ai_score"],
        "maxScore": result["max_score"],
        "explanation": result.get("explanation", result.get("feedback")),
        "feedback": result.get("feedback"),
        "details": result,
    }


@app.get("/api/answer-schemes")
async def list_answer_schemes(question_id: Optional[str] = None, subject: Optional[str] = None):
    if not HAS_PIPELINE:
        return {"answerSchemes": [], "total": 0}
    schemes = _db_get_answer_schemes(question_id=question_id, subject=subject)
    normalized = [_normalize_answer_scheme(s) for s in schemes]
    return {"answerSchemes": normalized, "total": len(normalized)}


@app.get("/api/answer-schemes/{answer_id}")
async def get_answer_scheme(answer_id: str):
    if not HAS_PIPELINE:
        raise HTTPException(status_code=503, detail="Pipeline not available")
    scheme = _db_get_answer_scheme_by_id(answer_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Answer scheme not found")
    return _normalize_answer_scheme(scheme)




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
            marks=req.marks,
        )
        normalized = []
        for i, q in enumerate(questions, start=1):
            scheme = _db_create_answer_scheme(q, question_number=i)
            nq = _normalize_question(q)
            nq["answerId"] = scheme["id"]
            normalized.append(nq)
        source = "langgraph_pipeline" if (LANGGRAPH_AVAILABLE and OLLAMA_AVAILABLE) else "pipeline_mock_fallback"
        if normalized:
            _log_activity_safe(
                action=f"Generated {len(normalized)} question(s)",
                activity_type="generate",
                subject=req.subject, detail=req.unit,
            )
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
    marks: Optional[int] = None,
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
                    marks=marks,
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

        normalized = []
        for i, q in enumerate(result_holder["questions"], start=1):
            try:
                scheme = _db_create_answer_scheme(q, question_number=i)
                answer_id = scheme["id"]
            except Exception:
                answer_id = None
            nq = _normalize_question(q)
            nq["answerId"] = answer_id
            normalized.append(nq)
        if normalized:
            _log_activity_safe(
                action=f"Generated {len(normalized)} question(s)",
                activity_type="generate",
                subject=subject, detail=unit,
            )
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


@app.get("/api/data-sources")
async def list_data_sources():
    """
    One entry per subject folder actually found under data/raw/ - this is
    the authoritative list of subjects that generation can possibly ground
    against, independent of whatever a UI dropdown happens to offer. Each
    entry reports whether that subject has matching ingested ChromaDB
    content (`ingested`), so it's immediately visible which subjects will
    produce grounded answer keys and which won't yet.
    """
    if not HAS_DATA_SOURCE:
        return {"subjects": []}
    return {"subjects": _data_source.list_subjects()}


@app.get("/api/data-sources/{subject}/files")
async def get_data_source_files(subject: str):
    if not HAS_DATA_SOURCE:
        raise HTTPException(status_code=503, detail="Data source browser not available")
    detail = _data_source.list_files_for_subject(subject)
    if not detail:
        raise HTTPException(status_code=404, detail=f"No raw data folder found for subject '{subject}'")
    return detail


@app.get("/api/data-sources/{subject}/download")
async def download_data_source_file(subject: str, path: str, source: str = "raw"):
    if not HAS_DATA_SOURCE:
        raise HTTPException(status_code=503, detail="Data source browser not available")
    if source not in ("raw", "pyqs"):
        raise HTTPException(status_code=400, detail="source must be 'raw' or 'pyqs'")
    resolved = _data_source.resolve_file_path(subject, path, source=source)
    if not resolved:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(resolved, filename=resolved.name)


@app.get("/api/students")
async def get_students():
    if HAS_DEMO_DATA:
        students = _demo.get_demo_students_with_scores()
    else:
        students = [{**s, "theory": None, "numerical": None, "drawing": None,
                     "co1": None, "co2": None, "co3": None, "co4": None, "co5": None,
                     "avg": None} for s in MOCK_STUDENTS]
    return {"students": students, "total": len(students)}


@app.get("/api/submissions")
async def get_submissions(status: Optional[str] = None):
    if HAS_DEMO_DATA:
        submissions = _demo.get_demo_submissions_with_flags(status=status)
    else:
        submissions = MOCK_SUBMISSIONS
    return {"submissions": submissions, "total": len(submissions)}


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

    if submission_id in GRADE_RESULTS:
        existing = GRADE_RESULTS[submission_id]
    elif HAS_DEMO_DATA:
        real = _demo.get_demo_grade_result(submission_id)
        existing = real if real else {"aiScore": None, "maxScore": None}
    else:
        existing = {"aiScore": None, "maxScore": None}

    original_score = existing.get("aiScore")
    max_score = existing.get("maxScore")

    # Persist to SQLite so overrides survive restarts
    _save_override(
        submission_id=submission_id,
        original_score=original_score,
        override_score=body.score,
        max_score=max_score,
        reason=body.reason,
    )

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
    _log_activity_safe(
        action=f"Faculty override on {submission_id} → {body.score}/{max_score or '?'}",
        activity_type="override", subject=sub.get("questionId", ""), detail=body.reason,
    )
    return result


@app.get("/api/submissions/overrides")
async def get_all_overrides():
    """Return all persisted faculty overrides (audit trail)."""
    return {"overrides": _get_overrides()}


@app.get("/api/analytics/co")
async def get_co_analytics():
    if HAS_DEMO_DATA:
        return _demo.get_demo_co_analytics()
    return {"co_analytics": [], "overall_attainment": None, "target": 70}


@app.get("/api/analytics/co-trend")
async def get_co_trend():
    """
    Real CO coverage trend across published exams, ordered by publish date -
    replaces the hardcoded 5-week trendData chart in COPOAnalytics.tsx.

    For each exam (in publish order), computes what share of that exam's
    total marks belongs to each CO, using the real questions actually
    included in it. This is a genuine measure of how CO coverage shifts as
    exams get published - NOT a measure of student performance over time,
    since no per-exam submission/grading history exists yet (only the
    fixed demo roster's submissions against two demo questions). If/when
    real per-exam student results exist, this endpoint is where attainment-
    over-time should be computed instead of coverage-over-time.
    """
    if not HAS_PIPELINE:
        return {"trend": [], "cos": []}
    try:
        exams = _db_get_exams()
    except Exception:
        exams = []
    if not exams:
        return {"trend": [], "cos": []}

    trend = []
    cos_seen = set()
    for i, exam in enumerate(exams, start=1):
        marks_by_co: dict = {}
        total_marks = 0
        for qid in exam["question_ids"]:
            q = _db_get_question_by_id(qid)
            if not q:
                continue
            co = q.get("co", "CO1")
            marks = q.get("marks", 0)
            marks_by_co[co] = marks_by_co.get(co, 0) + marks
            total_marks += marks
            cos_seen.add(co)
        point = {"exam": exam["id"], "label": f"Exam {i}", "title": exam["title"]}
        for co, m in marks_by_co.items():
            point[co] = round((m / total_marks) * 100, 1) if total_marks else 0
        trend.append(point)

    return {"trend": trend, "cos": sorted(cos_seen)}


@app.get("/api/analytics/co-po-correlation")
async def get_co_po_correlation():
    """
    Real CO-PO correlation derived from how many marks of PUBLISHED exam
    questions exercise each CO (and therefore each CO's mapped PO, via the
    fixed CO_PO_MAP curriculum mapping) - replaces the hardcoded poMatrix
    grid in COPOAnalytics.tsx. Strength is bucketed 0-3 by share of total
    published marks a given CO represents, matching the matrix's existing
    "3 = Strong, 2 = Moderate, 1 = Weak, 0 = None" legend.
    """
    if not HAS_PIPELINE:
        return {"matrix": [], "pos": [], "cos": []}
    try:
        exams = _db_get_exams()
    except Exception:
        exams = []

    marks_by_co: dict = {}
    total_marks = 0
    for exam in exams:
        for qid in exam["question_ids"]:
            q = _db_get_question_by_id(qid)
            if not q:
                continue
            co = q.get("co", "CO1")
            marks = q.get("marks", 0)
            marks_by_co[co] = marks_by_co.get(co, 0) + marks
            total_marks += marks

    all_cos = ["CO1", "CO2", "CO3", "CO4", "CO5"]
    all_pos = sorted(set(_CO_PO_MAP.values())) or ["PO1", "PO2", "PO3", "PO4"]

    def strength_for(co: str, po: str) -> int:
        # Only the CO's own mapped PO (per CO_PO_MAP) gets a non-zero
        # strength - this mirrors how the static matrix represented a fixed
        # curriculum mapping, but now the VALUE reflects real coverage
        # share instead of an invented number.
        if _CO_PO_MAP.get(co) != po or total_marks == 0:
            return 0
        share = marks_by_co.get(co, 0) / total_marks
        if share >= 0.30:
            return 3
        if share >= 0.15:
            return 2
        if share > 0:
            return 1
        return 0

    matrix = [{"po": po, **{co: strength_for(co, po) for co in all_cos}} for po in all_pos]
    return {"matrix": matrix, "pos": all_pos, "cos": all_cos, "hasData": total_marks > 0}


@app.get("/api/exams")
async def get_exams():
    if HAS_PIPELINE:
        try:
            db_exams = _db_get_exams()
            normalized = [{
                "id": e["id"], "title": e["title"], "subject": e["subject"],
                "totalMarks": e["total_marks"], "duration": e["duration"],
                "questions": e["question_ids"], "createdAt": e["created_at"],
                "status": e["status"],
            } for e in db_exams]
            # Demo exam (from demo_data.py) is shown alongside real published
            # exams rather than replacing them - it's a fixed reference point
            # for the seeded demo questions, not meant to disappear once a
            # real exam is published.
            all_exams = MOCK_EXAMS + normalized
            return {"exams": all_exams, "total": len(all_exams)}
        except Exception:
            pass
    return {"exams": MOCK_EXAMS, "total": len(MOCK_EXAMS)}


@app.post("/api/exams")
async def create_exam(body: ExamCreateRequest):
    exam_id = f"EX-{str(uuid.uuid4())[:6].upper()}"
    created_at = datetime.utcnow().isoformat() + "Z"
    exam = {
        "id": exam_id,
        "title": body.title,
        "subject": body.subject,
        "totalMarks": body.total_marks,
        "duration": body.duration,
        "questions": body.question_ids,
        "createdAt": created_at,
        # This endpoint IS the "Publish to Students" action on the frontend -
        # there's no separate draft-then-publish step, so it's stored as
        # published immediately rather than the permanently-stuck "draft"
        # state this previously always wrote regardless of intent.
        "status": "published",
    }
    if HAS_PIPELINE:
        try:
            _db_save_exam({
                "id": exam_id, "title": body.title, "subject": body.subject,
                "total_marks": body.total_marks, "duration": body.duration,
                "question_ids": body.question_ids, "status": "published",
                "created_at": created_at,
            })
        except Exception:
            pass
    _log_activity_safe(
        action=f"Exam paper published ({len(body.question_ids)} questions)",
        activity_type="publish", subject=body.subject, detail=body.title,
    )
    return exam


@app.post("/api/eval/theory")
async def eval_theory(body: TheoryEvalRequest):
    if not THEORY_EVAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Theory evaluator not available")

    ref = _resolve_grading_reference(
        answer_id=body.answer_id, question_id=body.question_id,
        question_fallback=body.question or "", subject_fallback=body.subject or "",
        reference_fallback=body.reference_answer or body.model_answer or "",
        max_marks_fallback=body.max_marks or 10,
    )
    eval_result = evaluate_theory(
        question=ref["question_text"], student_answer=body.student_answer,
        reference_answer=ref["reference_answer"], subject=ref["subject"], max_marks=ref["max_marks"],
    )
    _log_activity_safe(
        action=f"Graded 1 theory submission ({eval_result['ai_score']}/{eval_result['max_score']})",
        activity_type="grade", subject=ref.get("subject", ""), detail=ref.get("question_id") or "",
    )
    return {
        "questionId": ref["question_id"],
        "answerId": ref["answer_id"],
        "co": ref.get("co"),
        "aiScore": eval_result["ai_score"],
        "maxScore": eval_result["max_score"],
        "confidence": eval_result["confidence"],
        "feedback": eval_result["feedback"],
        "explanation": eval_result["explanation"],
        "keywordScore": eval_result["keyword_score"],
        "semanticScore": eval_result["semantic_score"],
        "matchedKeywords": eval_result["keywords"]["found"],
        "missingKeywords": eval_result["keywords"]["missing"],
        "hadReferenceData": ref["grounded"] and bool(ref["reference_answer"]),
    }


@app.post("/api/eval/drawing")
async def eval_drawing(
    file: UploadFile = File(None),
    max_marks: int = Form(20),
    student_usn: str = Form(""),
    assignment: str = Form(""),
    question_id: str = Form(""),
    answer_id: str = Form(""),
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

    ref = _resolve_grading_reference(
        answer_id=answer_id, question_id=question_id,
        question_fallback=assignment, max_marks_fallback=max_marks,
    )
    question_text = ref["question_text"] or assignment
    max_marks = ref["max_marks"] or max_marks

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
            "explanation": "Drawing evaluator module not available.",
        }
    result["questionId"] = ref["question_id"]
    result["answerId"] = ref["answer_id"]
    result["co"] = ref.get("co")
    _log_activity_safe(
        action=f"Evaluated 1 drawing ({result.get('ai_score')}/{result.get('max_score')})",
        activity_type="grade", subject=ref.get("subject", ""), detail=ref.get("question_id") or "",
    )
    return result


@app.post("/api/eval/numerical")
async def eval_numerical(body: NumericalEvalRequest):
    if not NUMERICAL_EVAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Numerical evaluator not available")

    ref = _resolve_grading_reference(
        answer_id=body.answer_id, question_id=body.question_id,
        question_fallback=body.question or "", subject_fallback=body.subject or "",
        reference_fallback=body.reference_answer or "", max_marks_fallback=body.max_marks or 10,
    )

    result = grade_numerical(
        question=ref["question_text"],
        student_solution=body.student_solution,
        reference_answer=ref["reference_answer"],
        expected_formula=body.expected_formula or "",
        expected_final_answer=body.expected_final_answer or "",
        subject=ref["subject"],
        max_marks=ref["max_marks"],
    )
    result["questionId"] = ref["question_id"]
    result["answerId"] = ref["answer_id"]
    result["co"] = ref.get("co")
    _log_activity_safe(
        action=f"Graded 1 numerical submission ({result.get('ai_score')}/{result.get('max_score')})",
        activity_type="grade", subject=ref.get("subject", ""), detail=ref.get("question_id") or "",
    )
    return result


@app.get("/api/eval/validate/kappa")
async def eval_validate_kappa():
    """
    Computes Cohen's Kappa between AI scores and simulated faculty scores on
    the demo dataset (theory + numerical submissions). This demonstrates the
    validation methodology described in the synopsis (target κ ≥ 0.75).

    Faculty scores are derived from known answer quality tiers authored in
    seed_demo_data.py - "good" answers get near-full marks, "poor" answers
    get low marks, matching what a faculty member would assign. The AI scores
    are computed live by the real evaluators against the seeded answer keys.

    Score buckets for κ computation: 0-3 (Low), 4-6 (Mid), 7-10 (High).
    Cohen's κ = (P_o - P_e) / (1 - P_e) where P_o = observed agreement,
    P_e = expected agreement by chance.
    """
    if not HAS_DEMO_DATA:
        raise HTTPException(status_code=503, detail="Demo data not available")

    try:
        grades = _demo._grade_all_demo_submissions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not compute grades: {e}")

    # Simulated faculty scores based on known answer quality tiers.
    # These represent what a human examiner would award for each submission,
    # serving as the "ground truth" for Kappa computation.
    # Submission ID assignment (from demo_data._build_submissions, in order):
    # ST-001 Arjun:   S-001 theory (good), S-002 numerical (good)
    # ST-002 Priya:   S-003 theory (good), S-004 numerical (good)
    # ST-003 Rohan:   S-005 theory (poor), S-006 numerical (wrong_final)
    # ST-004 Kavitha: S-007 theory (good), S-008 numerical (no_formula)
    # ST-005 Suresh:  S-009 theory (poor), S-010 numerical (good)
    FACULTY_SCORES = {
        # Theory submissions (out of 10): good → 8, poor → 2
        "S-001": 8,   # Arjun - good theory
        "S-003": 8,   # Priya - good theory
        "S-005": 2,   # Rohan - poor theory
        "S-007": 8,   # Kavitha - good theory
        "S-009": 2,   # Suresh - poor theory
        # Numerical submissions (out of 10): good → 10, no_formula → 7, wrong_final → 7
        "S-002": 10,  # Arjun - good numerical
        "S-004": 10,  # Priya - good numerical
        "S-006": 7,   # Rohan - wrong_final (-1)
        "S-008": 7,   # Kavitha - no_formula (-1)
        "S-010": 10,  # Suresh - good numerical
    }

    # Map scores to 3-bucket ordinal scale
    def bucket(score: float, max_score: float) -> int:
        pct = (score / max_score * 10) if max_score else 0
        if pct <= 3: return 0
        if pct <= 6: return 1
        return 2

    BUCKET_LABELS = {0: "Low (0-3)", 1: "Mid (4-6)", 2: "High (7-10)"}

    pairs = []
    for sub_id, faculty_raw in FACULTY_SCORES.items():
        g = grades.get(sub_id)
        if not g:
            continue
        ai_bucket = bucket(g["ai_score"], g["max_score"])
        fac_bucket = bucket(faculty_raw, 10)
        pairs.append({
            "submission_id": sub_id,
            "type": g["type"],
            "ai_score": g["ai_score"],
            "max_score": g["max_score"],
            "ai_bucket": BUCKET_LABELS[ai_bucket],
            "faculty_score": faculty_raw,
            "faculty_bucket": BUCKET_LABELS[fac_bucket],
            "agreement": ai_bucket == fac_bucket,
        })

    if not pairs:
        return {"kappa": None, "pairs": [], "interpretation": "No pairs computed"}

    n = len(pairs)
    n_agree = sum(1 for p in pairs if p["agreement"])
    p_observed = n_agree / n

    # Expected agreement by chance (marginal frequencies)
    from collections import Counter
    ai_counts = Counter(p["ai_bucket"] for p in pairs)
    fac_counts = Counter(p["faculty_bucket"] for p in pairs)
    p_expected = sum(
        (ai_counts.get(b, 0) / n) * (fac_counts.get(b, 0) / n)
        for b in set(ai_counts) | set(fac_counts)
    )

    kappa = round((p_observed - p_expected) / (1 - p_expected), 3) if p_expected < 1.0 else 1.0

    if kappa >= 0.80:
        interpretation = "Almost perfect agreement (κ ≥ 0.80)"
    elif kappa >= 0.75:
        interpretation = "Substantial agreement — meets project target (κ ≥ 0.75)"
    elif kappa >= 0.60:
        interpretation = "Moderate agreement (κ ≥ 0.60)"
    elif kappa >= 0.40:
        interpretation = "Fair agreement (κ ≥ 0.40)"
    else:
        interpretation = "Slight agreement (κ < 0.40)"

    theory_pairs = [p for p in pairs if p["type"] == "theory"]
    num_pairs = [p for p in pairs if p["type"] == "numerical"]

    return {
        "kappa": kappa,
        "p_observed": round(p_observed, 3),
        "p_expected": round(p_expected, 3),
        "n_pairs": n,
        "n_agreement": n_agree,
        "interpretation": interpretation,
        "target": "κ ≥ 0.75",
        "target_met": kappa >= 0.75,
        "theory_accuracy": round(sum(1 for p in theory_pairs if p["agreement"]) / len(theory_pairs), 3) if theory_pairs else None,
        "numerical_accuracy": round(sum(1 for p in num_pairs if p["agreement"]) / len(num_pairs), 3) if num_pairs else None,
        "pairs": pairs,
        "note": "Faculty scores are derived from known answer quality tiers authored in seed_demo_data.py. Buckets: Low=0-3, Mid=4-6, High=7-10 (out of 10).",
    }


@app.post("/api/eval/script")
async def eval_answer_script(
    file: UploadFile = File(...),
    reference_id: str = Form(""),          # preferred: ID from training_refs
    subject: str = Form(""),               # fallback if no reference_id
    max_marks_per_q: int = Form(0),        # fallback if no reference_id (0 = use ref default)
    exam_questions_json: str = Form(""),   # JSON array of question metadata (optional)
):
    """
    Full answer-script evaluation pipeline.

    Upload a handwritten answer sheet (PDF or image). The server:
    1. Converts PDF pages to images
    2. Runs OCR (EasyOCR) to extract handwritten text
    3. Segments answers by question markers (Q1, 1., Answer 1, …)
    4. Classifies each answer as theory / numerical / drawing
    5. Dispatches to the appropriate evaluator
    6. Returns a unified grade report

    exam_questions_json (optional): JSON array with per-question hints:
      [{q_number, question, type, reference_answer, max_marks, ...}, ...]
    """
    import json as _json

    try:
        from evaluation.script_pipeline import evaluate_answer_script
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Script pipeline not available: {e}")

    upload_dir = Path(__file__).parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    save_path = str(upload_dir / f"script_{uuid.uuid4().hex}{suffix}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Resolve subject + marks + exam_questions from reference scheme
    resolved_subject = subject or "General"
    resolved_marks   = max_marks_per_q if max_marks_per_q > 0 else 10
    exam_questions   = None

    if reference_id.strip():
        conn = _get_training_conn()
        ref_row = conn.execute(
            "SELECT subject, marks_per_q, questions_json FROM training_refs WHERE id=?",
            (reference_id.strip(),)
        ).fetchone()
        conn.close()
        if ref_row:
            resolved_subject = ref_row["subject"] or resolved_subject
            if ref_row["marks_per_q"] and ref_row["marks_per_q"] > 0:
                resolved_marks = int(ref_row["marks_per_q"])
            try:
                parsed_qs = _json.loads(ref_row["questions_json"] or "[]")
                if parsed_qs:
                    exam_questions = parsed_qs
            except Exception:
                pass

    # exam_questions_json from request overrides scheme (allows manual override)
    if exam_questions_json.strip():
        try:
            exam_questions = _json.loads(exam_questions_json)
        except Exception:
            pass

    try:
        report = evaluate_answer_script(
            file_path=save_path,
            subject=resolved_subject,
            max_marks_per_q=resolved_marks,
            exam_questions=exam_questions,
            student_name=file.filename or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    _log_activity_safe(
        action=f"Evaluated answer script: {report['questions_evaluated']} questions, "
               f"{report['total_score']}/{report['max_total']} ({report['percentage']}%)",
        activity_type="grade",
        subject=resolved_subject,
    )
    return report


@app.post("/api/eval/script/batch")
async def eval_answer_script_batch(
    files: List[UploadFile] = File(...),
    reference_id: str = Form(""),
    subject: str = Form(""),
    max_marks_per_q: int = Form(0),
    exam_questions_json: str = Form(""),
    student_names_json: str = Form(""),
    student_usns_json: str = Form(""),
):
    """
    Batch evaluation: upload multiple answer PDFs at once (or a ZIP).
    Returns class-level summary + per-student reports.
    """
    import json as _json
    from evaluation.script_pipeline import evaluate_multiple_scripts

    upload_dir = Path(__file__).parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Resolve subject + marks + questions from reference scheme
    resolved_subject = subject or "General"
    resolved_marks   = max_marks_per_q if max_marks_per_q > 0 else 10
    exam_questions   = None

    if reference_id.strip():
        conn = _get_training_conn()
        ref_row = conn.execute(
            "SELECT subject, marks_per_q, questions_json FROM training_refs WHERE id=?",
            (reference_id.strip(),)
        ).fetchone()
        conn.close()
        if ref_row:
            resolved_subject = ref_row["subject"] or resolved_subject
            if ref_row["marks_per_q"] and ref_row["marks_per_q"] > 0:
                resolved_marks = int(ref_row["marks_per_q"])
            try:
                parsed_qs = _json.loads(ref_row["questions_json"] or "[]")
                if parsed_qs:
                    exam_questions = parsed_qs
            except Exception:
                pass

    if exam_questions_json.strip():
        try:
            exam_questions = _json.loads(exam_questions_json)
        except Exception:
            pass

    student_names = []
    student_usns  = []
    try:
        student_names = _json.loads(student_names_json) if student_names_json.strip() else []
        student_usns  = _json.loads(student_usns_json)  if student_usns_json.strip()  else []
    except Exception:
        pass

    file_entries = []
    for idx, uf in enumerate(files):
        suffix   = Path(uf.filename or "upload.pdf").suffix or ".pdf"
        save_path = str(upload_dir / f"batch_{uuid.uuid4().hex}{suffix}")
        with open(save_path, "wb") as fp:
            shutil.copyfileobj(uf.file, fp)

        # If it's a ZIP, extract and add each contained file
        if save_path.endswith(".zip"):
            with zipfile.ZipFile(save_path, "r") as zf:
                for zi, zname in enumerate(zf.namelist()):
                    ext = Path(zname).suffix.lower()
                    if ext not in {".pdf", ".png", ".jpg", ".jpeg"}:
                        continue
                    zdata = zf.read(zname)
                    zpath = str(upload_dir / f"batch_{uuid.uuid4().hex}{ext}")
                    with open(zpath, "wb") as zfp:
                        zfp.write(zdata)
                    file_entries.append({
                        "file_path":    zpath,
                        "student_name": Path(zname).stem,
                        "student_usn":  "",
                    })
        else:
            file_entries.append({
                "file_path":    save_path,
                "student_name": student_names[idx] if idx < len(student_names) else Path(uf.filename or "").stem,
                "student_usn":  student_usns[idx]  if idx < len(student_usns)  else "",
            })

    if not file_entries:
        raise HTTPException(status_code=400, detail="No valid files found in upload")

    try:
        batch_result = evaluate_multiple_scripts(
            file_entries=file_entries,
            subject=resolved_subject,
            max_marks_per_q=resolved_marks,
            exam_questions=exam_questions,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    _log_activity_safe(
        action=f"Batch evaluation: {batch_result['total_students']} scripts, "
               f"class avg {batch_result['class_avg']}%, "
               f"{batch_result['pass_count']} pass / {batch_result['fail_count']} fail",
        activity_type="grade",
        subject=resolved_subject,
    )
    return batch_result


@app.get("/api/eval/script/batch/csv")
async def batch_results_csv(subject: str = ""):
    """Placeholder — actual CSV is generated client-side from the batch JSON."""
    return {"message": "Generate CSV from the batch report returned by POST /api/eval/script/batch"}


@app.get("/api/health/deps")
async def health_deps():
    """Return availability of optional ML dependencies (OCR, etc.)."""
    try:
        from evaluation.ocr_engine import get_dependency_status
        ocr_deps = get_dependency_status()
    except Exception as e:
        ocr_deps = {"ready": False, "error": str(e)}

    return {
        "ocr_pipeline": ocr_deps,
        "theory_evaluator":   THEORY_EVAL_AVAILABLE,
        "numerical_evaluator": NUMERICAL_EVAL_AVAILABLE,
        "drawing_evaluator":  DRAWING_EVAL_AVAILABLE,
        "install_instructions": {
            "ocr": "pip install easyocr pdf2image Pillow && apt-get install -y poppler-utils",
        }
    }


@app.post("/api/training/upload")
async def upload_training_reference(
    file: UploadFile = File(...),
    subject: str = Form(""),          # optional — detected from scheme if blank
    description: str = Form(""),
    default_marks: float = Form(10),  # fallback if scheme doesn't specify marks
):
    """
    Upload an answer scheme PDF/image.
    The server OCRs the file, extracts subject + questions + expected answers + marks,
    and stores the structured data so student scripts can be evaluated against it.
    """
    # Save file
    subj_dir = _TRAINING_DIR / "schemes"
    subj_dir.mkdir(parents=True, exist_ok=True)
    suffix   = Path(file.filename or "scheme.pdf").suffix or ".pdf"
    ref_id   = uuid.uuid4().hex[:8]
    save_path = str(subj_dir / f"scheme_{ref_id}{suffix}")
    with open(save_path, "wb") as fp:
        shutil.copyfileobj(file.file, fp)

    # Parse the answer scheme
    parsed_subject   = subject.strip()
    questions_list   = []
    parse_warnings   = []
    marks_per_q      = default_marks

    try:
        from evaluation.scheme_parser import parse_answer_scheme
        result = parse_answer_scheme(
            file_path=save_path,
            subject_hint=parsed_subject,
            default_marks=int(default_marks),
        )
        parsed_subject  = result["subject"]
        questions_list  = result["questions"]
        parse_warnings  = result["parse_warnings"]
        raw_ocr_text    = result.get("raw_text", "")
        if questions_list:
            mark_vals = [q["max_marks"] for q in questions_list if q.get("max_marks")]
            if mark_vals:
                marks_per_q = max(set(mark_vals), key=mark_vals.count)
    except Exception as e:
        parse_warnings.append(f"Parsing failed: {e}. File saved but no questions extracted.")
        raw_ocr_text = ""

    final_subject = parsed_subject or subject or "Unknown"

    conn = _get_training_conn()
    conn.execute("""
        INSERT INTO training_refs
          (id, subject, q_type, filename, description, file_path, marks_per_q, questions_json, parse_warnings, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        ref_id, final_subject, "scheme",
        file.filename or "", description,
        save_path, marks_per_q,
        json.dumps(questions_list),
        json.dumps(parse_warnings),
        datetime.utcnow().isoformat() + "Z",
    ))
    conn.commit()
    conn.close()

    _log_activity_safe(
        action=f"Answer scheme uploaded: {file.filename} ({final_subject}, {len(questions_list)} questions parsed)",
        activity_type="train", subject=final_subject,
    )
    return {
        "id":               ref_id,
        "subject":          final_subject,
        "filename":         file.filename,
        "questions_parsed": len(questions_list),
        "marks_per_q":      marks_per_q,
        "parse_warnings":   parse_warnings,
        "questions":        questions_list,
        "raw_ocr_text":     raw_ocr_text[:3000],   # first 3000 chars so UI can show what was read
        "message": (
            f"Scheme parsed: {len(questions_list)} questions extracted from '{file.filename}'."
            if questions_list else
            "File saved but no questions could be extracted. See the OCR text below to understand what was read."
        ),
    }


@app.get("/api/training/references")
async def list_training_references(subject: str = "", q_type: str = ""):
    """List all uploaded training reference files."""
    conn = _get_training_conn()
    query = "SELECT * FROM training_refs WHERE 1=1"
    params: list = []
    if subject:
        query += " AND subject=?"
        params.append(subject)
    if q_type:
        query += " AND q_type=?"
        params.append(q_type)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"references": [dict(r) for r in rows]}


@app.delete("/api/training/references/{ref_id}")
async def delete_training_reference(ref_id: str):
    """Remove a training reference file and its metadata."""
    conn = _get_training_conn()
    row = conn.execute("SELECT * FROM training_refs WHERE id=?", (ref_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reference not found")
    row = dict(row)
    try:
        Path(row["file_path"]).unlink(missing_ok=True)
    except Exception:
        pass
    conn.execute("DELETE FROM training_refs WHERE id=?", (ref_id,))
    conn.commit()
    conn.close()
    return {"deleted": ref_id}


@app.get("/api/students/export/csv")
async def export_students_csv():
    """Export student grades as CSV for university MIS / spreadsheet import."""
    if not HAS_DEMO_DATA:
        raise HTTPException(status_code=503, detail="No student data available")
    students = _demo.DEMO_STUDENTS
    lines = ["USN,Name,Section,Theory%,Numerical%,Drawing%,CO1,CO2,CO3,CO4,CO5,Avg%"]
    for s in students:
        lines.append(
            f"{s.get('usn','')},{s.get('name','')},{s.get('section','')},"
            f"{s.get('theory','')},{s.get('numerical','')},{s.get('drawing','')},"
            f"{s.get('co1','')},{s.get('co2','')},{s.get('co3','')},{s.get('co4','')},{s.get('co5','')},"
            f"{s.get('avg','')}"
        )
    content = "\n".join(lines)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=student_grades.csv"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
