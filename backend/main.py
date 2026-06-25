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
from fastapi.responses import StreamingResponse, FileResponse
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
    from evaluation.unified_evaluator import evaluate as unified_evaluate
    UNIFIED_EVAL_AVAILABLE = True
except ImportError:
    UNIFIED_EVAL_AVAILABLE = False

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

class UnifiedEvalRequest(BaseModel):
    """Unified evaluation: accepts text or image, auto-detects question type."""
    student_answer: Optional[str] = ""
    answer_id: Optional[str] = None
    question_id: Optional[str] = None
    question: Optional[str] = ""
    subject: Optional[str] = ""
    reference_answer: Optional[str] = ""
    max_marks: Optional[int] = 10
    question_type: Optional[str] = "auto"
    expected_formula: Optional[str] = ""
    expected_final_answer: Optional[str] = ""

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
EVAL_HISTORY: list = []

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


@app.post("/api/data-sources/upload")
async def upload_and_ingest(
    subject: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """
    Upload PDF/DOCX files organized by unit and ingest into ChromaDB.

    Each file's original path (from webkitRelativePath) encodes the unit:
      SubjectFolder/Unit-1/file.pdf  →  unit = "Unit 1"
      SubjectFolder/file.pdf         →  unit extracted from filename

    After saving to data/raw/{subject}/, runs the ingestion pipeline
    (load → enrich metadata → chunk → store in ChromaDB with SQLite fallback).
    """
    import shutil

    DATA_DIR = Path(__file__).parent.parent / "data"
    RAW_DIR = DATA_DIR / "raw"
    CHROMA_DIR = DATA_DIR / "db" / "chroma"
    ALLOWED = {".pdf", ".docx", ".doc", ".txt", ".pptx"}

    subject_dir = RAW_DIR / subject
    subject_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for upload_file in files:
        ext = Path(upload_file.filename).suffix.lower()
        if ext not in ALLOWED:
            continue

        parts = Path(upload_file.filename).parts
        if len(parts) >= 2:
            unit_folder = parts[-2]
        else:
            unit_folder = None

        if unit_folder:
            dest_dir = subject_dir / unit_folder
        else:
            dest_dir = subject_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / Path(upload_file.filename).name
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(upload_file.file, f)
        saved_files.append(str(dest_path.relative_to(RAW_DIR)))

    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid files uploaded")

    chunk_count = 0
    ingest_error = None
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from ingestion.pipeline import load_documents
        from ingestion.metadata_extractor import enrich_metadata
        from chunking.chunker import chunk_docs

        docs = load_documents(str(subject_dir))
        if docs:
            docs = enrich_metadata(docs)
            for doc in docs:
                doc.metadata["subject"] = subject
            chunks = chunk_docs(docs)
            chunk_count = len(chunks)

            if chunks:
                db_path = str(CHROMA_DIR / subject)
                try:
                    from vector_store.chroma_client import create_vector_db
                    vectordb = create_vector_db(chunks, persist_directory=db_path)
                    if vectordb is None:
                        raise RuntimeError("Embedding model unavailable")
                except Exception:
                    _ingest_to_sqlite_fallback(chunks, db_path, subject)
    except Exception as e:
        ingest_error = str(e)

    result = {
        "subject": subject,
        "filesUploaded": len(saved_files),
        "files": saved_files,
        "chunksIngested": chunk_count,
    }
    if ingest_error:
        result["ingestWarning"] = f"Files saved but ingestion had an error: {ingest_error}"
    return result


def _ingest_to_sqlite_fallback(chunks, persist_dir: str, subject: str):
    """Store chunks in SQLite mimicking ChromaDB's schema for fallback retrieval."""
    import sqlite3 as _sqlite3
    os.makedirs(persist_dir, exist_ok=True)
    db_path = os.path.join(persist_dir, "chroma.sqlite3")
    conn = _sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_metadata (
            id INTEGER, key TEXT, string_value TEXT,
            int_value INTEGER, float_value REAL, bool_value INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_em_key ON embedding_metadata(key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_em_id ON embedding_metadata(id)")
    existing = conn.execute("SELECT COALESCE(MAX(id), -1) FROM embedding_metadata").fetchone()[0]
    next_id = existing + 1
    for i, chunk in enumerate(chunks):
        cid = next_id + i
        meta = chunk.metadata
        rows = [
            (cid, "chroma:document", chunk.page_content, None, None, None),
            (cid, "subject", meta.get("subject", subject), None, None, None),
            (cid, "unit", meta.get("unit", "Unknown"), None, None, None),
            (cid, "source_file", meta.get("source_file", ""), None, None, None),
        ]
        conn.executemany("INSERT INTO embedding_metadata VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


@app.post("/api/data-sources/{subject}/reingest")
async def reingest_subject(subject: str):
    """Re-run ingestion for a subject that already has files in data/raw/."""
    DATA_DIR = Path(__file__).parent.parent / "data"
    RAW_DIR = DATA_DIR / "raw"
    CHROMA_DIR = DATA_DIR / "db" / "chroma"

    subject_dir = RAW_DIR / subject
    if not subject_dir.exists():
        raise HTTPException(status_code=404, detail=f"No raw data for '{subject}'")

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from ingestion.pipeline import load_documents
        from ingestion.metadata_extractor import enrich_metadata
        from chunking.chunker import chunk_docs

        docs = load_documents(str(subject_dir))
        if not docs:
            raise HTTPException(status_code=400, detail="No usable documents found")

        docs = enrich_metadata(docs)
        for doc in docs:
            doc.metadata["subject"] = subject
        chunks = chunk_docs(docs)

        db_path = str(CHROMA_DIR / subject)
        try:
            from vector_store.chroma_client import create_vector_db
            vectordb = create_vector_db(chunks, persist_directory=db_path)
            if vectordb is None:
                raise RuntimeError("Embedding model unavailable")
        except Exception:
            _ingest_to_sqlite_fallback(chunks, db_path, subject)

        return {"subject": subject, "chunksIngested": len(chunks)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        action=f"Faculty override on {submission_id} (score: {body.score})",
        activity_type="override", subject=sub.get("questionId", ""), detail=body.reason,
    )
    return result


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


# ── Unified Evaluation Endpoint ──────────────────────────────────────────────

def _check_pdf_deps():
    """Check PDF dependencies on startup and print instructions if missing."""
    available = []
    missing = []
    for pkg, imp in [("pypdf", "pypdf"), ("PyMuPDF", "fitz"), ("PyPDF2", "PyPDF2")]:
        try:
            __import__(imp)
            available.append(pkg)
        except ImportError:
            missing.append(pkg)
    if not available:
        print("\n" + "=" * 60)
        print("WARNING: No PDF extraction library found!")
        print("PDF scheme parsing will NOT work.")
        print("Install at least one: pip install pypdf PyMuPDF")
        print("=" * 60 + "\n")
    else:
        print(f"[PDF] Available extractors: {', '.join(available)}")
    return available

_PDF_AVAILABLE = _check_pdf_deps()


def _extract_text_from_pdf(pdf_path: str) -> str:
    # Try pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[PDF] pypdf failed for {pdf_path}: {e}")

    # Try PyMuPDF (fitz)
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[PDF] PyMuPDF failed for {pdf_path}: {e}")

    # Try PyPDF2 (older, might be installed)
    try:
        from PyPDF2 import PdfReader as PdfReader2
        reader = PdfReader2(pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[PDF] PyPDF2 failed for {pdf_path}: {e}")

    # Try PyPDFLoader (langchain)
    try:
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        text = "\n".join(p.page_content for p in pages if p.page_content.strip())
        if text.strip():
            return text
    except Exception as e:
        print(f"[PDF] PyPDFLoader failed for {pdf_path}: {e}")

    print(f"[PDF] All extractors failed for {pdf_path}")
    print(f"[PDF] Install a PDF library: pip install pypdf PyMuPDF")
    return ""


def _parse_answer_scheme(pdf_text: str) -> list:
    """Extract structured questions from answer scheme text.
    Uses heuristic parser first (reliable for structured schemes), falls back to LLM."""
    if not pdf_text.strip():
        return []

    # Try heuristic parser first — it handles the full document
    heuristic_result = _heuristic_parse_scheme(pdf_text)

    # If heuristic found multiple real questions (not the single-question fallback), use it
    if len(heuristic_result) > 1:
        total_m = sum(q['marks'] for q in heuristic_result)
        print(f"[parse-scheme] Heuristic parser found {len(heuristic_result)} questions, total: {total_m} marks")
        for q in heuristic_result:
            print(f"  Q{q['question_number']}: {q['marks']}m ({q['question_type']}) - {q['question_text'][:70]}")
        return heuristic_result

    # Fallback to LLM for unstructured documents
    if OLLAMA_AVAILABLE:
        try:
            prompt = f"""You are parsing an exam answer scheme / marking scheme document.
Extract EVERY question from the document. For each question determine:
- question_number: the question number (1, 2, 3a, etc.)
- question_text: the full question text
- reference_answer: the model/expected answer or marking points
- marks: the maximum marks for this question (integer)
- question_type: "theory" or "numerical" or "drawing" based on content
- expected_formula: any formula the student should use (or empty string)
- expected_final_answer: the expected final numerical answer if applicable (or empty string)

DOCUMENT:
{pdf_text[:12000]}

Respond ONLY in JSON format:
{{
  "questions": [
    {{
      "question_number": "1",
      "question_text": "...",
      "reference_answer": "...",
      "marks": 10,
      "question_type": "theory",
      "expected_formula": "",
      "expected_final_answer": ""
    }}
  ]
}}
Output ONLY valid JSON. No markdown or explanation."""

            import ollama as _ollama
            resp = _ollama.chat(
                model=os.getenv("OLLAMA_MODEL", "mistral"),
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1},
            )
            text = resp["message"]["content"].strip()
            import re as _re
            cleaned = _re.sub(r'```(?:json)?', '', text).strip()
            start = cleaned.find('{')
            if start != -1:
                depth = 0
                for i in range(start, len(cleaned)):
                    if cleaned[i] == '{': depth += 1
                    elif cleaned[i] == '}':
                        depth -= 1
                        if depth == 0:
                            parsed = json.loads(cleaned[start:i+1])
                            llm_result = parsed.get("questions", [])
                            if len(llm_result) > len(heuristic_result):
                                print(f"[parse-scheme] LLM parser found {len(llm_result)} questions")
                                return llm_result
        except Exception as e:
            print(f"[parse-scheme] LLM parsing failed: {e}")

    if heuristic_result:
        total_m = sum(q['marks'] for q in heuristic_result)
        print(f"[parse-scheme] Heuristic fallback: {len(heuristic_result)} questions, total: {total_m} marks")
        return heuristic_result

    return []


def _heuristic_parse_scheme(text: str) -> list:
    """Regex-based fallback to extract questions when LLM is unavailable."""
    import re as _re
    questions = []
    lines = text.split('\n')

    q_header_with_marks = _re.compile(r'^\s*Q\.?\s*(\d+(?:\.\d+|[a-e])?)\s*\.?\s+(.+?)\s*\((\d+)\s*[Mm]arks?\)', _re.IGNORECASE)
    q_header_q_prefix = _re.compile(r'^\s*Q\.?\s*(\d+(?:\.\d+|[a-e])?)\s*\.?\s+([A-Za-z].+)', _re.IGNORECASE)
    q_header_pattern = _re.compile(r'^\s*(\d+(?:\.\d+|[a-e])?)\s+([A-Za-z].+)', _re.IGNORECASE)
    q_number_only = _re.compile(r'^\s*(\d+(?:\.\d+|[a-e]))\s*$')
    marks_line_pattern = _re.compile(r'^(\d{1,2})\s+\d+\s+\d+\s*$')
    # Also match marks at end of a line: "...question text 6 3 2"
    trailing_marks = _re.compile(r'\s+(\d{1,2})\s+\d+\s+\d+\s*$')
    inline_marks = _re.compile(r'\[?\s*(\d+)\s*(?:marks?|pts?|points?)\s*\]?', _re.IGNORECASE)
    total_marks_line = _re.compile(r'Total\s+(\d+)\s*Marks', _re.IGNORECASE)
    page_line = _re.compile(r'^\d+\s*\|\s*P\s*a\s*g\s*e')
    skip_lines = _re.compile(r'^(PART\s*[–\-]\s*[A-Z]|Q\.\s*$|No\s+Question|Academic Year|Department of|Date:|Semester:|Course)', _re.IGNORECASE)

    has_q_prefix = bool(_re.search(r'^\s*Q\.?\s*\d', text, _re.MULTILINE | _re.IGNORECASE))

    segments = []
    current_qnum = None
    current_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or page_line.match(stripped) or skip_lines.match(stripped):
            continue
        if stripped.lower().startswith('no question m bt co') or stripped.lower() == 'question m bt co':
            continue

        hm_match = q_header_with_marks.match(stripped)
        qp_match = q_header_q_prefix.match(stripped) if not hm_match else None
        header_match = q_header_pattern.match(stripped) if not hm_match and not qp_match and not has_q_prefix else None
        numonly_match = q_number_only.match(stripped) if not hm_match and not qp_match and not header_match and not has_q_prefix else None

        if hm_match:
            if current_qnum:
                segments.append((current_qnum, current_lines))
            current_qnum = hm_match.group(1)
            q_text_part = hm_match.group(2).strip()
            header_marks = hm_match.group(3)
            current_lines = [q_text_part, f"__marks__:{header_marks}"] if q_text_part else [f"__marks__:{header_marks}"]
        elif qp_match:
            if current_qnum:
                segments.append((current_qnum, current_lines))
            current_qnum = qp_match.group(1)
            q_text_part = qp_match.group(2).strip()
            # Check for (X Marks) at end of text
            paren_marks = _re.search(r'\((\d+)\s*[Mm]arks?\)\s*$', q_text_part)
            if paren_marks:
                q_text_part = q_text_part[:paren_marks.start()].strip()
                current_lines = [q_text_part, f"__marks__:{paren_marks.group(1)}"]
            else:
                current_lines = [q_text_part] if q_text_part else []
        elif header_match:
            if current_qnum:
                segments.append((current_qnum, current_lines))
            current_qnum = header_match.group(1)
            q_text_part = header_match.group(2).strip()
            tm = trailing_marks.search(q_text_part)
            if tm:
                q_text_part = q_text_part[:tm.start()].strip()
                current_lines = [q_text_part, stripped[tm.start():].strip()] if q_text_part else [stripped[tm.start():].strip()]
            else:
                current_lines = [q_text_part] if q_text_part else []
        elif numonly_match:
            if current_qnum:
                segments.append((current_qnum, current_lines))
            current_qnum = numonly_match.group(1)
            current_lines = []
        elif current_qnum is not None:
            current_lines.append(stripped)

    if current_qnum:
        segments.append((current_qnum, current_lines))

    for q_num, content_lines in segments:
        marks = 0
        filtered = []
        for cl in content_lines:
            if cl.startswith("__marks__:"):
                marks = int(cl.split(":")[1])
                continue
            m = marks_line_pattern.match(cl.strip())
            if m:
                marks = int(m.group(1))
            else:
                filtered.append(cl)

        # Look for "Total X Marks" in content
        if not marks:
            for cl in reversed(filtered):
                tm = total_marks_line.search(cl)
                if tm:
                    marks = int(tm.group(1))
                    break
        # Look for inline marks like "[5 marks]" or "5 Marks"
        if not marks:
            for cl in filtered:
                im = inline_marks.search(cl)
                if im:
                    candidate = int(im.group(1))
                    if 1 <= candidate <= 20:
                        marks = candidate
                        break
        # Last resort: look for the LAST standalone number line (M BT CO where only M is on a line)
        if not marks:
            for cl in reversed(content_lines):
                stripped_cl = cl.strip()
                if _re.match(r'^(\d{1,2})\s*$', stripped_cl):
                    candidate = int(stripped_cl)
                    if 1 <= candidate <= 20:
                        marks = candidate
                        break
        if not marks:
            marks = 10

        q_text = filtered[0] if filtered else f"Question {q_num}"
        ref_answer = '\n'.join(filtered[1:]) if len(filtered) > 1 else ""

        q_type = "theory"
        q_lower = q_text.lower()
        if any(c in q_lower for c in ["calculate", "compute", "find the value", "determine", "solve", "numerical"]):
            q_type = "numerical"
        elif any(c in q_lower for c in ["draw", "sketch", "diagram", "orthographic", "isometric"]):
            q_type = "drawing"

        questions.append({
            "question_number": q_num,
            "question_text": q_text,
            "reference_answer": ref_answer,
            "marks": marks,
            "question_type": q_type,
            "expected_formula": "",
            "expected_final_answer": "",
        })

    if not questions and text.strip():
        questions.append({
            "question_number": "1",
            "question_text": text[:200],
            "reference_answer": text,
            "marks": 10,
            "question_type": "theory",
            "expected_formula": "",
            "expected_final_answer": "",
        })

    return questions


@app.post("/api/eval/debug-pdf")
async def debug_pdf(scheme_pdf: UploadFile = File(...)):
    """Debug endpoint: returns raw extracted text from a PDF."""
    upload_dir = Path(__file__).parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in (scheme_pdf.filename or "debug.pdf"))
    pdf_path = str(upload_dir / f"debug_{safe_name}")
    content = await scheme_pdf.read()
    with open(pdf_path, "wb") as f:
        f.write(content)
    pdf_text = _extract_text_from_pdf(pdf_path)
    lines = pdf_text.split("\n")
    return {
        "text_length": len(pdf_text),
        "line_count": len(lines),
        "lines": [{"num": i, "text": line} for i, line in enumerate(lines)],
        "raw_text": pdf_text,
    }


@app.post("/api/eval/parse-scheme")
async def parse_scheme_pdf(
    scheme_pdf: UploadFile = File(...),
):
    """Parse an answer scheme PDF and return structured questions with marks and types."""
    upload_dir = Path(__file__).parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in (scheme_pdf.filename or "scheme.pdf"))
    pdf_path = str(upload_dir / f"scheme_{safe_name}")

    content = await scheme_pdf.read()
    print(f"[parse-scheme] Received file: {scheme_pdf.filename}, size: {len(content)} bytes, saving to: {pdf_path}")
    if len(content) < 100:
        raise HTTPException(status_code=400, detail=f"PDF file too small ({len(content)} bytes). Upload may have failed.")

    with open(pdf_path, "wb") as f:
        f.write(content)

    pdf_text = _extract_text_from_pdf(pdf_path)
    if not pdf_text:
        file_size = os.path.getsize(pdf_path)
        raise HTTPException(status_code=400, detail=f"Could not extract text from PDF ({file_size} bytes on disk). All PDF extractors failed — check server logs.")
    questions = _parse_answer_scheme(pdf_text)
    print(f"[parse-scheme] Extracted {len(questions)} questions from {scheme_pdf.filename}, text length: {len(pdf_text)}")
    return {"questions": questions, "raw_text": pdf_text[:2000], "total": len(questions)}


@app.post("/api/eval/batch")
async def eval_batch(
    files: List[UploadFile] = File(...),
    scheme_pdf: UploadFile = File(None),
    questions_json: str = Form("[]"),
    subject: str = Form(""),
    student_text: str = Form(""),
):
    """Evaluate multiple student scripts against parsed answer scheme questions.
    questions_json is a JSON array of question objects from parse-scheme."""
    if not UNIFIED_EVAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Unified evaluator not available")

    upload_dir = Path(__file__).parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    parsed_questions = json.loads(questions_json) if questions_json else []

    if not parsed_questions and scheme_pdf and scheme_pdf.filename:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in scheme_pdf.filename)
        pdf_path = str(upload_dir / f"scheme_{safe_name}")
        content = await scheme_pdf.read()
        with open(pdf_path, "wb") as f:
            f.write(content)
        pdf_text = _extract_text_from_pdf(pdf_path)
        parsed_questions = _parse_answer_scheme(pdf_text)

    if not parsed_questions:
        raise HTTPException(status_code=400, detail="No questions found in answer scheme")

    all_results = []
    for student_file in files:
        if not student_file.filename:
            continue
        safe_fn = "".join(c if c.isalnum() or c in "._-" else "_" for c in student_file.filename)
        file_save_path = str(upload_dir / safe_fn)
        file_content = await student_file.read()
        with open(file_save_path, "wb") as f:
            f.write(file_content)

        file_text = ""
        image_path = None
        if student_file.filename.lower().endswith(".pdf"):
            file_text = _extract_text_from_pdf(file_save_path)
        elif student_file.filename.lower().endswith(".txt"):
            with open(file_save_path, "r", encoding="utf-8", errors="ignore") as tf:
                file_text = tf.read()
        else:
            image_path = file_save_path

        if not file_text and student_text:
            file_text = student_text

        student_name = student_file.filename.rsplit(".", 1)[0]
        import concurrent.futures

        def _eval_q(q):
            return unified_evaluate(
                question=q.get("question_text", ""),
                student_answer=file_text,
                answer_image_path=image_path,
                reference_answer=q.get("reference_answer", ""),
                max_marks=q.get("marks", 10),
                subject=subject,
                question_type=q.get("question_type", "auto"),
                expected_formula=q.get("expected_formula", ""),
                expected_final_answer=q.get("expected_final_answer", ""),
            )

        question_results = []
        total_score = 0
        total_max = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(parsed_questions), 6)) as executor:
            futures = {executor.submit(_eval_q, q): q for q in parsed_questions}
            for future in concurrent.futures.as_completed(futures):
                q = futures[future]
                q_result = future.result()
                q_result["question_number"] = q.get("question_number", "")
                q_result["question_text"] = q.get("question_text", "")
                question_results.append(q_result)
                total_score += q_result.get("ai_score", 0)
                total_max += q_result.get("max_score", 0)

        question_results.sort(key=lambda r: r.get("question_number", ""))

        student_record = {
            "student_name": student_name,
            "script_file": student_file.filename,
            "total_score": round(total_score, 1),
            "total_max": total_max,
            "question_results": question_results,
            "ocr_used": any(r.get("ocr_used") for r in question_results),
            "avg_confidence": round(sum(r.get("confidence", 0) for r in question_results) / max(len(question_results), 1), 2),
        }

        eval_id = f"EVAL-{str(uuid.uuid4())[:8].upper()}"
        history_record = {
            "id": eval_id,
            "student_name": student_name,
            "question": f"{len(parsed_questions)} questions from answer scheme",
            "subject": subject,
            "question_type": "mixed",
            "ai_score": round(total_score, 1),
            "max_score": total_max,
            "confidence": student_record["avg_confidence"],
            "ocr_used": student_record["ocr_used"],
            "ocr_method": "llava" if student_record["ocr_used"] else "pdf",
            "feedback": f"Evaluated against {len(parsed_questions)} questions. Total: {round(total_score, 1)}/{total_max}",
            "explanation": "; ".join(
                f"Q{r['question_number']}: {r.get('ai_score', 0)}/{r.get('max_score', 0)}"
                for r in question_results
            ),
            "overridden": False,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
            "script_file": student_file.filename,
            "question_results": question_results,
        }
        EVAL_HISTORY.insert(0, history_record)
        student_record["eval_id"] = eval_id
        all_results.append(student_record)

    _log_activity_safe(
        action=f"Batch evaluated {len(all_results)} scripts against {len(parsed_questions)} questions",
        activity_type="grade", subject=subject,
    )

    return {
        "results": all_results,
        "total_students": len(all_results),
        "total_questions": len(parsed_questions),
        "questions": parsed_questions,
    }


@app.post("/api/eval/unified")
async def eval_unified(
    file: UploadFile = File(None),
    scheme_pdf: UploadFile = File(None),
    student_answer: str = Form(""),
    student_name: str = Form(""),
    answer_id: str = Form(""),
    question_id: str = Form(""),
    question: str = Form(""),
    subject: str = Form(""),
    reference_answer: str = Form(""),
    max_marks: int = Form(10),
    question_type: str = Form("auto"),
    expected_formula: str = Form(""),
    expected_final_answer: str = Form(""),
    save_history: str = Form("false"),
):
    if not UNIFIED_EVAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="Unified evaluator not available")

    upload_dir = Path(__file__).parent.parent / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Parse answer scheme PDF if provided
    parsed_questions = []
    if scheme_pdf and scheme_pdf.filename:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in scheme_pdf.filename)
        pdf_path = str(upload_dir / f"scheme_{safe_name}")
        scheme_content = await scheme_pdf.read()
        with open(pdf_path, "wb") as f:
            f.write(scheme_content)
        scheme_text = _extract_text_from_pdf(pdf_path)
        if scheme_text:
            parsed_questions = _parse_answer_scheme(scheme_text)
            if not reference_answer and not parsed_questions:
                reference_answer = scheme_text
            if not question and not parsed_questions:
                lines = [l.strip() for l in scheme_text.split("\n") if l.strip()]
                if lines:
                    question = lines[0]

    image_path = None
    if file and file.filename:
        safe_fn = "".join(c if c.isalnum() or c in "._-" else "_" for c in file.filename)
        file_save_path = str(upload_dir / safe_fn)
        file_bytes = await file.read()
        with open(file_save_path, "wb") as f:
            f.write(file_bytes)
        if file.filename.lower().endswith(".pdf"):
            pdf_text = _extract_text_from_pdf(file_save_path)
            if pdf_text and not student_answer:
                student_answer = pdf_text
        else:
            image_path = file_save_path

    # Multi-question scheme: evaluate each question and return batch-style results
    if len(parsed_questions) > 1:
        import concurrent.futures

        def _eval_one(q):
            return unified_evaluate(
                question=q.get("question_text", ""),
                student_answer=student_answer,
                answer_image_path=image_path,
                reference_answer=q.get("reference_answer", ""),
                max_marks=q.get("marks", 10),
                subject=subject,
                question_type=q.get("question_type", "auto"),
                expected_formula=q.get("expected_formula", ""),
                expected_final_answer=q.get("expected_final_answer", ""),
            )

        question_results = []
        total_score = 0
        total_max = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(parsed_questions), 6)) as executor:
            futures = {executor.submit(_eval_one, q): q for q in parsed_questions}
            for future in concurrent.futures.as_completed(futures):
                q = futures[future]
                q_result = future.result()
                q_result["question_number"] = q.get("question_number", "")
                q_result["question_text"] = q.get("question_text", "")
                question_results.append(q_result)
                total_score += q_result.get("ai_score", 0)
                total_max += q_result.get("max_score", 0)

        question_results.sort(key=lambda r: r.get("question_number", ""))

        student_name_val = student_name or (file.filename.rsplit(".", 1)[0] if file and file.filename else "Unknown")
        student_record = {
            "student_name": student_name_val,
            "script_file": file.filename if file and file.filename else "typed_answer",
            "total_score": round(total_score, 1),
            "total_max": total_max,
            "question_results": question_results,
            "ocr_used": any(r.get("ocr_used") for r in question_results),
            "avg_confidence": round(sum(r.get("confidence", 0) for r in question_results) / max(len(question_results), 1), 2),
        }

        eval_id = f"EVAL-{str(uuid.uuid4())[:8].upper()}"
        history_record = {
            "id": eval_id,
            "student_name": student_name_val,
            "question": f"{len(parsed_questions)} questions from answer scheme",
            "subject": subject,
            "question_type": "mixed",
            "ai_score": round(total_score, 1),
            "max_score": total_max,
            "confidence": student_record["avg_confidence"],
            "ocr_used": student_record["ocr_used"],
            "ocr_method": "llava" if student_record["ocr_used"] else "pdf",
            "feedback": f"Evaluated against {len(parsed_questions)} questions. Total: {round(total_score, 1)}/{total_max}",
            "explanation": "; ".join(
                f"Q{r['question_number']}: {r.get('ai_score', 0)}/{r.get('max_score', 0)}"
                for r in question_results
            ),
            "overridden": False,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
            "script_file": file.filename if file and file.filename else None,
            "question_results": question_results,
        }
        EVAL_HISTORY.insert(0, history_record)
        student_record["eval_id"] = eval_id

        _log_activity_safe(
            action=f"Evaluated 1 script against {len(parsed_questions)} questions ({round(total_score, 1)}/{total_max})",
            activity_type="grade", subject=subject,
        )
        return {
            "batch": True,
            "results": [student_record],
            "total_students": 1,
            "total_questions": len(parsed_questions),
            "questions": parsed_questions,
        }

    ref = _resolve_grading_reference(
        answer_id=answer_id or None, question_id=question_id or None,
        question_fallback=question or "", subject_fallback=subject or "",
        reference_fallback=reference_answer or "",
        max_marks_fallback=max_marks or 10,
    )

    result = unified_evaluate(
        question=ref["question_text"] or question,
        student_answer=student_answer,
        answer_image_path=image_path,
        reference_answer=ref["reference_answer"] or reference_answer,
        max_marks=ref["max_marks"] or max_marks,
        subject=ref["subject"] or subject,
        question_type=question_type,
        expected_formula=expected_formula,
        expected_final_answer=expected_final_answer,
    )

    result["questionId"] = ref["question_id"]
    result["answerId"] = ref["answer_id"]
    result["co"] = ref.get("co")
    result["hadReferenceData"] = ref["grounded"] and bool(ref["reference_answer"])

    if save_history.lower() == "true":
        eval_id = f"EVAL-{str(uuid.uuid4())[:8].upper()}"
        record = {
            "id": eval_id,
            "student_name": student_name or "Unknown",
            "question": (ref["question_text"] or question)[:200],
            "subject": ref["subject"] or subject,
            "question_type": result.get("question_type", "theory"),
            "ai_score": result.get("ai_score", 0),
            "max_score": result.get("max_score", max_marks),
            "confidence": result.get("confidence", 0),
            "ocr_used": result.get("ocr_used", False),
            "ocr_method": result.get("ocr_method", "none"),
            "feedback": result.get("feedback", ""),
            "explanation": result.get("explanation", ""),
            "overridden": False,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
            "script_file": file.filename if file and file.filename else None,
        }
        EVAL_HISTORY.insert(0, record)
        result["eval_id"] = eval_id

    _log_activity_safe(
        action=f"Evaluated 1 {result.get('question_type', 'unified')} submission "
               f"({result.get('ai_score')}/{result.get('max_score')})",
        activity_type="grade", subject=ref.get("subject", ""),
        detail=ref.get("question_id") or "",
    )
    return result


@app.get("/api/eval/history")
async def get_eval_history():
    return {"evaluations": EVAL_HISTORY, "total": len(EVAL_HISTORY)}


@app.post("/api/eval/history/{eval_id}/override")
async def override_eval(eval_id: str, body: OverrideRequest):
    rec = next((r for r in EVAL_HISTORY if r["id"] == eval_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Evaluation record not found")
    rec["overridden"] = True
    rec["override_score"] = body.score
    rec["override_reason"] = body.reason
    rec["overridden_by"] = "faculty"
    rec["overridden_at"] = datetime.utcnow().isoformat() + "Z"
    _log_activity_safe(
        action=f"Faculty override on {eval_id} ({rec['ai_score']} → {body.score})",
        activity_type="override", subject=rec.get("subject", ""), detail=body.reason,
    )
    return rec


@app.delete("/api/eval/history/{eval_id}")
async def delete_eval(eval_id: str):
    global EVAL_HISTORY
    before = len(EVAL_HISTORY)
    EVAL_HISTORY = [r for r in EVAL_HISTORY if r["id"] != eval_id]
    if len(EVAL_HISTORY) == before:
        raise HTTPException(status_code=404, detail="Evaluation record not found")
    return {"success": True, "id": eval_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
