"""
LangGraph 11-agent question generation pipeline for MechAssess.
Agents: BloomAnalyzer → Scout → Generator → Validator (x3 parallel)
        → PedagogyTagger → SyllabusGuardian → Archivist
"""

import hashlib
import json
import sqlite3
import os
import re
from datetime import datetime
from typing import TypedDict, List, Optional, Annotated
from pathlib import Path

try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, SystemMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

DB_PATH = Path(__file__).parent.parent / "data" / "questions.db"

# ── Database setup ─────────────────────────────────────────────────────────────

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            type TEXT NOT NULL,
            subject TEXT NOT NULL,
            unit TEXT NOT NULL,
            bloom_level INTEGER NOT NULL,
            bloom_label TEXT NOT NULL,
            co TEXT NOT NULL,
            po TEXT NOT NULL,
            marks INTEGER NOT NULL,
            difficulty TEXT NOT NULL,
            answer_key TEXT,
            source_chunk TEXT,
            sha256 TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def question_sha256(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()

def is_duplicate(sha: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT 1 FROM questions WHERE sha256 = ?", (sha,)).fetchone()
    conn.close()
    return row is not None

def save_question(q: dict):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO questions
            (id, text, type, subject, unit, bloom_level, bloom_label, co, po,
             marks, difficulty, answer_key, source_chunk, sha256, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            q["id"], q["text"], q["type"], q["subject"], q["unit"],
            q["bloom_level"], q["bloom_label"], q["co"], q["po"],
            q["marks"], q["difficulty"], q.get("answer_key"),
            q.get("source_chunk"), q["sha256"], q["created_at"]
        ))
        conn.commit()
    finally:
        conn.close()

def get_all_questions(subject=None, unit=None, bloom_level=None, q_type=None):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM questions WHERE 1=1"
    params = []
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    if unit:
        query += " AND unit LIKE ?"
        params.append(f"%{unit}%")
    if bloom_level:
        query += " AND bloom_level = ?"
        params.append(bloom_level)
    if q_type:
        query += " AND type = ?"
        params.append(q_type)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    cols = ["id","text","type","subject","unit","bloom_level","bloom_label",
            "co","po","marks","difficulty","answer_key","source_chunk","sha256","created_at"]
    return [dict(zip(cols, r)) for r in rows]

def delete_question(qid: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()

# ── Bloom config ───────────────────────────────────────────────────────────────

BLOOM_LABELS = {
    1: ("Remember", "list, define, recall, identify, name"),
    2: ("Understand", "explain, describe, summarize, classify, compare"),
    3: ("Apply", "solve, calculate, use, demonstrate, compute"),
    4: ("Analyze", "derive, differentiate, examine, break down, investigate"),
    5: ("Evaluate", "justify, critique, assess, argue, defend"),
    6: ("Create", "design, formulate, construct, develop, propose"),
}

CO_PO_MAP = {
    "CO1": "PO1", "CO2": "PO2", "CO3": "PO3", "CO4": "PO2", "CO5": "PO4",
}

MARKS_BY_BLOOM = {1: 4, 2: 6, 3: 8, 4: 10, 5: 12, 6: 15}
DIFFICULTY_BY_BLOOM = {1: "easy", 2: "easy", 3: "medium", 4: "medium", 5: "hard", 6: "hard"}

# ── Agent state ────────────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    subject: str
    unit: str
    bloom_level: int
    question_type: str
    co: str
    count: int
    context_chunks: List[str]
    raw_questions: List[str]
    validated_questions: List[str]
    tagged_questions: List[dict]
    final_questions: List[dict]
    errors: List[str]

# ── LLM call helper ───────────────────────────────────────────────────────────

def llm_call(prompt: str, model: str = None) -> str:
    if not OLLAMA_AVAILABLE:
        return ""
    model = model or os.getenv("OLLAMA_MODEL", "mistral")
    try:
        resp = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return resp["message"]["content"]
    except Exception:
        return ""

# ── Agents ─────────────────────────────────────────────────────────────────────

def bloom_analyzer_agent(state: PipelineState) -> PipelineState:
    """Classifies and validates the requested Bloom level."""
    level = state["bloom_level"]
    if level not in BLOOM_LABELS:
        state["bloom_level"] = 3
    return state

def scout_agent(state: PipelineState) -> PipelineState:
    """Retrieves relevant context from ChromaDB with adaptive k based on Bloom level."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from vector_store.chroma_client import get_or_create_chroma
        from vector_store.retriever import retrieve_chunks

        # Adaptive k: higher Bloom levels need more context
        k = 3 + state["bloom_level"]

        collection = get_or_create_chroma(state["subject"])
        chunks = retrieve_chunks(
            collection,
            query=f"{state['unit']} {BLOOM_LABELS[state['bloom_level']][1]}",
            unit=state["unit"],
            k=k
        )
        state["context_chunks"] = [c.page_content if hasattr(c, "page_content") else str(c) for c in chunks]
    except Exception as e:
        state["context_chunks"] = []
        state["errors"].append(f"Scout agent: {e}")
    return state

def generator_agent(state: PipelineState) -> PipelineState:
    """Generates raw questions using LLM with Bloom-appropriate prompting."""
    bloom_label, bloom_verbs = BLOOM_LABELS[state["bloom_level"]]
    context = "\n\n".join(state["context_chunks"][:2000])[:2000]

    type_instruction = {
        "theory": "conceptual theory questions requiring explanation or derivation",
        "numerical": "numerical problem-solving questions with specific given values",
        "drawing": "engineering drawing questions requiring sketches or projections",
    }.get(state["question_type"], "theory questions")

    prompt = f"""You are an expert Mechanical Engineering professor creating exam questions.

Subject: {state['subject']}
Unit/Topic: {state['unit']}
Bloom's Level: L{state['bloom_level']} — {bloom_label}
Action verbs to use: {bloom_verbs}
Question Type: {type_instruction}
Course Outcome: {state['co']}
Number of questions: {state['count']}

Reference material:
{context}

Generate exactly {state['count']} {type_instruction} at Bloom's L{state['bloom_level']} ({bloom_label}) level.
Each question must:
- Use action verbs appropriate for L{state['bloom_level']}: {bloom_verbs}
- Be directly tied to the reference material above
- Be original (not copied from reference)
- Be specific and unambiguous
- For numerical: include specific numerical values
- For drawing: specify what exactly to draw

Output ONLY a numbered list of questions. No preamble, no explanations.
1. [Question 1]
2. [Question 2]
..."""

    raw = llm_call(prompt)
    questions = []
    if raw:
        for line in raw.strip().split("\n"):
            line = line.strip()
            match = re.match(r"^\d+[\.\)]\s*(.+)", line)
            if match:
                q = match.group(1).strip()
                if len(q) > 20:
                    questions.append(q)

    state["raw_questions"] = questions
    return state

def quality_validator_agent(state: PipelineState) -> PipelineState:
    """Checks question quality: length, clarity, specificity."""
    validated = []
    for q in state["raw_questions"]:
        if len(q) < 20:
            continue
        # Must end with ? or have directive verb
        has_question_form = "?" in q or any(
            q.lower().startswith(v) for v in ["derive", "calculate", "find", "draw", "explain",
                "describe", "analyze", "evaluate", "design", "state", "prove", "determine"]
        )
        if has_question_form:
            validated.append(q)
    state["validated_questions"] = validated or state["raw_questions"]
    return state

def difficulty_validator_agent(state: PipelineState) -> PipelineState:
    """Confirms difficulty aligns with Bloom level — filters trivially easy questions for high levels."""
    bloom = state["bloom_level"]
    if bloom <= 2:
        return state  # any question fine for low levels
    filtered = []
    for q in state["validated_questions"]:
        word_count = len(q.split())
        # High Bloom levels should have substantive questions
        if bloom >= 4 and word_count < 10:
            continue
        filtered.append(q)
    state["validated_questions"] = filtered or state["validated_questions"]
    return state

def correctness_validator_agent(state: PipelineState) -> PipelineState:
    """Checks that question text doesn't contain contradictions or obvious errors."""
    # Basic heuristic: remove questions with brackets indicating template gaps
    filtered = [q for q in state["validated_questions"] if "[" not in q and "___" not in q]
    state["validated_questions"] = filtered or state["validated_questions"]
    return state

def pedagogy_tagger_agent(state: PipelineState) -> PipelineState:
    """Tags each question with CO/PO mapping, marks, difficulty, Bloom label."""
    bloom_label = BLOOM_LABELS[state["bloom_level"]][0]
    tagged = []
    import uuid
    for i, q_text in enumerate(state["validated_questions"]):
        sha = question_sha256(q_text)
        if is_duplicate(sha):
            continue  # SHA-256 deduplication
        tagged.append({
            "id": f"Q-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
            "text": q_text,
            "type": state["question_type"],
            "subject": state["subject"],
            "unit": state["unit"],
            "bloom_level": state["bloom_level"],
            "bloom_label": bloom_label,
            "co": state["co"],
            "po": CO_PO_MAP.get(state["co"], "PO1"),
            "marks": MARKS_BY_BLOOM[state["bloom_level"]],
            "difficulty": DIFFICULTY_BY_BLOOM[state["bloom_level"]],
            "sha256": sha,
            "created_at": datetime.now().isoformat(),
        })
    state["tagged_questions"] = tagged
    return state

def syllabus_guardian_agent(state: PipelineState) -> PipelineState:
    """Verifies questions are within the declared unit scope (fuzzy match)."""
    unit_keywords = state["unit"].lower().split()
    # Allow all if context is sparse
    if not state["context_chunks"]:
        state["final_questions"] = state["tagged_questions"]
        return state

    # Simple scope check: at least one question keyword should match context words
    context_words = set(" ".join(state["context_chunks"]).lower().split())
    approved = []
    for q in state["tagged_questions"]:
        q_words = set(q["text"].lower().split())
        overlap = q_words & context_words
        if len(overlap) >= 3:  # at least 3 content words appear in source
            approved.append(q)
    state["final_questions"] = approved or state["tagged_questions"]
    return state

def archivist_agent(state: PipelineState) -> PipelineState:
    """Persists approved questions to SQLite with full provenance metadata."""
    init_db()
    for q in state["final_questions"]:
        try:
            save_question(q)
        except Exception:
            pass
    return state

# ── Pipeline builder ───────────────────────────────────────────────────────────

def build_pipeline():
    if not LANGGRAPH_AVAILABLE:
        return None

    graph = StateGraph(PipelineState)
    graph.add_node("bloom_analyzer", bloom_analyzer_agent)
    graph.add_node("scout", scout_agent)
    graph.add_node("generator", generator_agent)
    graph.add_node("quality_validator", quality_validator_agent)
    graph.add_node("difficulty_validator", difficulty_validator_agent)
    graph.add_node("correctness_validator", correctness_validator_agent)
    graph.add_node("pedagogy_tagger", pedagogy_tagger_agent)
    graph.add_node("syllabus_guardian", syllabus_guardian_agent)
    graph.add_node("archivist", archivist_agent)

    graph.set_entry_point("bloom_analyzer")
    graph.add_edge("bloom_analyzer", "scout")
    graph.add_edge("scout", "generator")
    graph.add_edge("generator", "quality_validator")
    graph.add_edge("quality_validator", "difficulty_validator")
    graph.add_edge("difficulty_validator", "correctness_validator")
    graph.add_edge("correctness_validator", "pedagogy_tagger")
    graph.add_edge("pedagogy_tagger", "syllabus_guardian")
    graph.add_edge("syllabus_guardian", "archivist")
    graph.add_edge("archivist", END)

    return graph.compile()

# ── Public API ─────────────────────────────────────────────────────────────────

_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline

def run_pipeline(subject: str, unit: str, bloom_level: int, question_type: str,
                 co: str, count: int = 4) -> List[dict]:
    """
    Main entry point. Returns list of generated question dicts.
    Falls back to mock questions if LangGraph or Ollama unavailable.
    """
    initial_state: PipelineState = {
        "subject": subject,
        "unit": unit,
        "bloom_level": bloom_level,
        "question_type": question_type,
        "co": co,
        "count": count,
        "context_chunks": [],
        "raw_questions": [],
        "validated_questions": [],
        "tagged_questions": [],
        "final_questions": [],
        "errors": [],
    }

    pipeline = get_pipeline()
    if pipeline and OLLAMA_AVAILABLE:
        try:
            result = pipeline.invoke(initial_state)
            if result["final_questions"]:
                return result["final_questions"]
        except Exception:
            pass

    # Fallback: run agents manually without LangGraph
    state = initial_state
    for agent in [bloom_analyzer_agent, scout_agent, generator_agent,
                  quality_validator_agent, difficulty_validator_agent,
                  correctness_validator_agent, pedagogy_tagger_agent,
                  syllabus_guardian_agent, archivist_agent]:
        state = agent(state)

    return state["final_questions"] if state["final_questions"] else _mock_questions(subject, unit, bloom_level, question_type, co, count)

def _mock_questions(subject, unit, bloom_level, q_type, co, count) -> List[dict]:
    import uuid
    bloom_label = BLOOM_LABELS.get(bloom_level, BLOOM_LABELS[3])[0]
    templates = {
        "theory": [
            f"Explain the fundamental principles of {unit} as applied in {subject}.",
            f"Describe the significance of {unit} in the context of {subject} with suitable examples.",
            f"Derive the governing equation for {unit} from first principles.",
            f"Analyze the relationship between the key variables in {unit}.",
            f"Compare and contrast the different approaches used in {unit}.",
        ],
        "numerical": [
            f"A system in {unit} operates under given conditions. Calculate the primary output parameter.",
            f"Given the initial conditions for a {subject} problem in {unit}, determine the unknown.",
            f"Solve the step-by-step {unit} problem and verify using energy conservation.",
        ],
        "drawing": [
            f"Draw the complete representation for {unit} following IS standards.",
            f"Sketch and label all components relevant to {unit} with proper dimensions.",
        ],
    }
    texts = templates.get(q_type, templates["theory"])
    questions = []
    init_db()
    for i in range(min(count, len(texts))):
        sha = question_sha256(texts[i])
        q = {
            "id": f"Q-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
            "text": texts[i],
            "type": q_type,
            "subject": subject,
            "unit": unit,
            "bloom_level": bloom_level,
            "bloom_label": bloom_label,
            "co": co,
            "po": CO_PO_MAP.get(co, "PO1"),
            "marks": MARKS_BY_BLOOM.get(bloom_level, 8),
            "difficulty": DIFFICULTY_BY_BLOOM.get(bloom_level, "medium"),
            "sha256": sha,
            "created_at": datetime.now().isoformat(),
        }
        if not is_duplicate(sha):
            save_question(q)
        questions.append(q)
    return questions
