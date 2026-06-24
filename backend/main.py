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
        create_answer_scheme as _db_create_answer_scheme,
        get_answer_schemes as _db_get_answer_schemes,
        get_answer_scheme_by_id as _db_get_answer_scheme_by_id,
        get_answer_scheme_by_question_id as _db_get_answer_scheme_by_question_id,
        LANGGRAPH_AVAILABLE,
        OLLAMA_AVAILABLE,
    )
    HAS_PIPELINE = True
except Exception as _import_err:
    HAS_PIPELINE = False
    LANGGRAPH_AVAILABLE = False
    OLLAMA_AVAILABLE = False

try:
    import demo_data as _demo
    HAS_DEMO_DATA = True
except Exception:
    HAS_DEMO_DATA = False

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
    if HAS_PIPELINE:
        try:
            total_questions = len(_db_get_questions())
        except Exception:
            total_questions = 0

    demo_stats = _demo.get_demo_stats() if HAS_DEMO_DATA else {
        "activeExams": 0, "submissionsPending": 0, "avgCOAttainment": None,
        "totalStudents": 0, "gradedToday": 0,
    }

    return {
        "totalQuestions": total_questions,
        **demo_stats,
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
        questions, drop_reasons = _db_run_pipeline_for_specs(
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
    if HAS_DEMO_DATA:
        return _demo.get_demo_co_analytics()
    return {"co_analytics": [], "overall_attainment": None, "target": 70}


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
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
