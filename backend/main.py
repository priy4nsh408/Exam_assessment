"""
MechAssess FastAPI Backend
RVCE Mechanical Engineering AI Assessment Platform
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import uuid
import random
import sys
import os
from datetime import datetime, timedelta

# Try to import generation pipeline; fall back gracefully
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generation'))
    from generator import generate_questions as _gen_questions
    HAS_GENERATOR = True
except ImportError:
    HAS_GENERATOR = False

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from evaluation.theory_evaluator import evaluate_theory
    THEORY_EVAL_AVAILABLE = True
except ImportError:
    THEORY_EVAL_AVAILABLE = False

try:
    from evaluation.numerical_grader import grade_numerical
    NUMERICAL_GRADER_AVAILABLE = True
except ImportError:
    NUMERICAL_GRADER_AVAILABLE = False

app = FastAPI(title="MechAssess API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic schemas ─────────────────────────────────────────────────────────

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

# ─── Mock data stores ─────────────────────────────────────────────────────────

MOCK_QUESTIONS = [
    {
        "id": "Q-001", "text": "State and explain the zeroth law of thermodynamics.",
        "type": "theory", "subject": "Thermodynamics", "unit": "Unit 1",
        "bloomLevel": 1, "bloomLabel": "Remember", "co": "CO1", "po": "PO1",
        "marks": 4, "difficulty": "easy", "createdAt": "2026-05-01T10:00:00Z"
    },
    {
        "id": "Q-002", "text": "Derive the expression for work done in an isothermal process for an ideal gas.",
        "type": "theory", "subject": "Thermodynamics", "unit": "Unit 1",
        "bloomLevel": 4, "bloomLabel": "Analyze", "co": "CO1", "po": "PO1",
        "marks": 8, "difficulty": "medium", "createdAt": "2026-05-01T10:05:00Z"
    },
    {
        "id": "Q-003", "text": "A Carnot engine operating between 800 K and 400 K produces 150 kW. Calculate the heat supplied from the source and heat rejected to the sink.",
        "type": "numerical", "subject": "Thermodynamics", "unit": "Unit 2",
        "bloomLevel": 3, "bloomLabel": "Apply", "co": "CO2", "po": "PO2",
        "marks": 8, "difficulty": "medium", "createdAt": "2026-05-02T09:00:00Z"
    },
    {
        "id": "Q-004", "text": "Draw the SFD and BMD for a simply supported beam of span 6m with a point load of 20 kN at the center.",
        "type": "drawing", "subject": "Strength of Materials", "unit": "Unit 2",
        "bloomLevel": 3, "bloomLabel": "Apply", "co": "CO3", "po": "PO2",
        "marks": 10, "difficulty": "medium", "createdAt": "2026-05-02T11:00:00Z"
    },
    {
        "id": "Q-005", "text": "Explain Bernoulli's theorem with assumptions and derive the Bernoulli equation from Euler's equation of motion.",
        "type": "theory", "subject": "Fluid Mechanics", "unit": "Unit 2",
        "bloomLevel": 2, "bloomLabel": "Understand", "co": "CO4", "po": "PO1",
        "marks": 6, "difficulty": "easy", "createdAt": "2026-05-03T10:00:00Z"
    },
    {
        "id": "Q-006", "text": "Water flows through a pipe of diameter 200 mm at 3 m/s. Determine the Reynolds number and classify the flow. (dynamic viscosity = 0.001 Pa s, density = 1000 kg/m3)",
        "type": "numerical", "subject": "Fluid Mechanics", "unit": "Unit 4",
        "bloomLevel": 3, "bloomLabel": "Apply", "co": "CO4", "po": "PO2",
        "marks": 6, "difficulty": "easy", "createdAt": "2026-05-03T10:30:00Z"
    },
    {
        "id": "Q-007", "text": "Draw the first angle orthographic projections (front view, top view, and left side view) of a cylinder of diameter 50 mm and height 80 mm with a through hole of diameter 20 mm along the axis.",
        "type": "drawing", "subject": "Engineering Drawing", "unit": "Unit 1",
        "bloomLevel": 3, "bloomLabel": "Apply", "co": "CO5", "po": "PO3",
        "marks": 15, "difficulty": "hard", "createdAt": "2026-05-04T09:00:00Z"
    },
    {
        "id": "Q-008", "text": "Evaluate the change in entropy when 2 kg of steam at 200 deg C condenses at constant pressure of 1 MPa. Use steam tables.",
        "type": "numerical", "subject": "Thermodynamics", "unit": "Unit 1",
        "bloomLevel": 5, "bloomLabel": "Evaluate", "co": "CO1", "po": "PO2",
        "marks": 10, "difficulty": "hard", "createdAt": "2026-05-04T11:00:00Z"
    },
]

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
        "type": "theory", "content": "The zeroth law states that...",
        "submittedAt": "2026-05-10T09:15:00Z", "status": "graded"
    },
    {
        "id": "S-032", "studentId": "ST-002", "questionId": "Q-002",
        "type": "theory", "content": "For isothermal process, T = constant...",
        "submittedAt": "2026-05-10T09:18:00Z", "status": "graded"
    },
    {
        "id": "S-033", "studentId": "ST-003", "questionId": "Q-003",
        "type": "numerical", "content": "eta = 1 - T2/T1 = 1 - 400/800 = 0.5",
        "submittedAt": "2026-05-10T09:20:00Z", "status": "pending"
    },
    {
        "id": "S-034", "studentId": "ST-004", "questionId": "Q-003",
        "type": "numerical", "content": "eta = 1 - 300/900 = 0.667...",
        "submittedAt": "2026-05-10T09:25:00Z", "status": "pending"
    },
]

MOCK_EXAMS = [
    {
        "id": "EX-001", "title": "Thermodynamics Mid-Semester Examination",
        "subject": "Thermodynamics", "totalMarks": 50, "duration": 90,
        "questions": ["Q-001", "Q-002", "Q-003", "Q-008"],
        "createdAt": "2026-05-08T10:00:00Z", "status": "published"
    },
    {
        "id": "EX-002", "title": "Fluid Mechanics Unit Test — Unit 2 & 3",
        "subject": "Fluid Mechanics", "totalMarks": 30, "duration": 60,
        "questions": ["Q-005", "Q-006"],
        "createdAt": "2026-05-09T10:00:00Z", "status": "draft"
    },
    {
        "id": "EX-003", "title": "Strength of Materials — Bending & Torsion",
        "subject": "Strength of Materials", "totalMarks": 40, "duration": 90,
        "questions": ["Q-004"],
        "createdAt": "2026-05-10T10:00:00Z", "status": "draft"
    },
]

GRADE_RESULTS = {}

# ─── Helper: mock question generation ────────────────────────────────────────

def generate_mock_questions(req: QuestionGenerateRequest) -> list:
    bloom_labels = {1: 'Remember', 2: 'Understand', 3: 'Apply', 4: 'Analyze', 5: 'Evaluate', 6: 'Create'}
    templates = {
        'theory': [
            f"State and explain the fundamental principles of {req.unit.split(':')[-1].strip()} with relevant examples from mechanical engineering practice.",
            f"Derive the governing equations for {req.unit.split(':')[-1].strip()} starting from first principles. State all assumptions clearly.",
            f"Compare and contrast the key concepts in {req.unit.split(':')[-1].strip()}. Discuss the engineering significance of each.",
            f"Analyze the role of {req.unit.split(':')[-1].strip()} in modern mechanical systems. Provide three real-world applications.",
        ],
        'numerical': [
            f"A mechanical system operating under conditions defined by {req.unit.split(':')[-1].strip()} has the following parameters: [given data]. Calculate the efficiency, power output, and identify the limiting factor.",
            f"For a system governed by the principles of {req.unit.split(':')[-1].strip()}: given initial conditions, determine the final state and calculate the net work done.",
            f"Solve the following problem based on {req.unit.split(':')[-1].strip()}: A component with specified dimensions and material properties is subjected to loading. Find the maximum stress, strain, and factor of safety.",
            f"Using the equations of {req.unit.split(':')[-1].strip()}, analyze the given system and determine all relevant performance parameters. Plot the characteristic curve.",
        ],
        'drawing': [
            f"Draw the first angle orthographic projections of a {req.unit.split(':')[-1].strip()} component showing front view, top view, and left side view with complete dimensioning.",
            f"Sketch the isometric view of the given {req.unit.split(':')[-1].strip()} component. Include all dimensions and surface finish symbols as per IS standards.",
            f"Prepare a sectional drawing through the axis of symmetry of the {req.unit.split(':')[-1].strip()} object. Apply appropriate hatching and add title block.",
        ]
    }
    q_type = req.question_type if req.question_type in templates else 'theory'
    texts = templates[q_type]
    difficulties = ['easy', 'medium', 'hard']
    pos = ['PO1', 'PO2', 'PO3']

    questions = []
    for i in range(min(req.count, len(texts))):
        questions.append({
            "id": f"Q-{random.randint(100, 999)}",
            "text": texts[i % len(texts)],
            "type": q_type,
            "subject": req.subject,
            "unit": req.unit,
            "bloomLevel": req.bloom_level,
            "bloomLabel": bloom_labels.get(req.bloom_level, 'Apply'),
            "co": req.co,
            "po": pos[i % len(pos)],
            "marks": req.marks,
            "difficulty": difficulties[i % len(difficulties)],
            "createdAt": datetime.utcnow().isoformat() + "Z"
        })
    return questions


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    return {
        "totalQuestions": len(MOCK_QUESTIONS),
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
    if HAS_GENERATOR:
        try:
            questions = _gen_questions(
                subject=req.subject,
                unit=req.unit,
                bloom_level=req.bloom_level,
                question_type=req.question_type,
                co=req.co,
                count=req.count,
                marks=req.marks,
            )
            return {"questions": questions, "source": "langraph_pipeline"}
        except Exception as e:
            # Fall through to mock
            pass

    questions = generate_mock_questions(req)
    return {"questions": questions, "source": "mock_fallback"}


@app.get("/api/questions")
async def get_questions(
    subject: Optional[str] = None,
    type: Optional[str] = None,
    bloom_level: Optional[int] = None,
    co: Optional[str] = None,
):
    questions = list(MOCK_QUESTIONS)
    if subject:
        questions = [q for q in questions if q["subject"] == subject]
    if type:
        questions = [q for q in questions if q["type"] == type]
    if bloom_level:
        questions = [q for q in questions if q["bloomLevel"] == bloom_level]
    if co:
        questions = [q for q in questions if q["co"] == co]
    return {"questions": questions, "total": len(questions)}


@app.delete("/api/questions/{question_id}")
async def delete_question(question_id: str):
    q = next((q for q in MOCK_QUESTIONS if q["id"] == question_id), None)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"success": True, "id": question_id}


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
        "feedback": "Answer demonstrates good conceptual understanding. Some key derivations require elaboration. Terminology usage is appropriate for the subject domain.",
        "co": "CO1",
        "po": "PO1",
        "isOverridden": False,
        "gradedAt": datetime.utcnow().isoformat() + "Z"
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
        "overriddenAt": datetime.utcnow().isoformat() + "Z"
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
            "bloomCoverage": {"L1": 12, "L2": 18, "L3": 20, "L4": 15, "L5": 8, "L6": 3}
        },
        {
            "co": "CO2",
            "description": "Analyze power cycles and refrigeration systems",
            "averageAttainment": 65.1,
            "studentsAchieved": 40,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 8, "L2": 14, "L3": 22, "L4": 18, "L5": 10, "L6": 4}
        },
        {
            "co": "CO3",
            "description": "Solve problems in strength of materials and structural analysis",
            "averageAttainment": 82.4,
            "studentsAchieved": 51,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 10, "L2": 15, "L3": 25, "L4": 20, "L5": 12, "L6": 5}
        },
        {
            "co": "CO4",
            "description": "Apply fluid mechanics principles to flow analysis",
            "averageAttainment": 71.3,
            "studentsAchieved": 44,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 9, "L2": 16, "L3": 21, "L4": 17, "L5": 9, "L6": 2}
        },
        {
            "co": "CO5",
            "description": "Interpret and produce engineering drawings per IS standards",
            "averageAttainment": 88.0,
            "studentsAchieved": 55,
            "totalStudents": 62,
            "target": 70,
            "bloomCoverage": {"L1": 6, "L2": 12, "L3": 28, "L4": 14, "L5": 7, "L6": 3}
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
        "status": "draft"
    }
    MOCK_EXAMS.append(exam)
    return exam


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "generator_available": HAS_GENERATOR,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# ─── Evaluation endpoints ──────────────────────────────────────────────────────

class TheoryEvalRequest(BaseModel):
    question: str
    student_answer: str
    subject: str
    model_answer: str = ""
    max_marks: int = 10

@app.post("/api/eval/theory")
async def eval_theory(req: TheoryEvalRequest):
    if THEORY_EVAL_AVAILABLE:
        result = evaluate_theory(
            req.question, req.student_answer, req.subject,
            req.model_answer, req.max_marks
        )
    else:
        result = {
            "ai_score": 6.0, "max_score": req.max_marks,
            "concept_score": 3.0, "detail_score": 3.0,
            "confidence": 0.72, "feedback": "Theory evaluator not available.",
            "keywords": {"found": [], "missing": [], "coverage_ratio": 0},
            "similarity": 0.5,
        }
    return result


class NumericalGradeRequest(BaseModel):
    question: str
    student_solution: str
    subject: str = "Thermodynamics"
    rubric_steps: list = []
    max_marks: int = 10

@app.post("/api/eval/numerical")
async def eval_numerical(req: NumericalGradeRequest):
    if NUMERICAL_GRADER_AVAILABLE:
        result = grade_numerical(
            req.question, req.student_solution,
            req.rubric_steps or None, req.subject, req.max_marks
        )
    else:
        result = {"ai_score": 5.0, "max_score": req.max_marks,
                  "steps": [], "feedback": "Numerical grader not available.", "confidence": 0.4}
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
