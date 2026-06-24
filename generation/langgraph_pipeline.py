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
            generation_explanation TEXT,
            answer_key_explanation TEXT,
            sha256 TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
    """)
    # Migration for DBs created before these two columns existed.
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(questions)").fetchall()}
    for col in ("generation_explanation", "answer_key_explanation"):
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE questions ADD COLUMN {col} TEXT")

    # Answer schemes: the answer key for a question, addressable by its own
    # id (separate from the question's id). One question currently has one
    # active scheme, but giving it its own identity supports future
    # versioning/re-grading without losing history, and lets graders be
    # pointed at "answer_id" directly instead of always going via the question.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS answer_schemes (
            id TEXT PRIMARY KEY,
            question_id TEXT NOT NULL,
            question_text TEXT,
            question_number INTEGER,
            subject TEXT,
            type TEXT,
            marks INTEGER,
            answer_key TEXT,
            explanation TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Real activity log, replacing the old hardcoded "Recent Activity" feed
    # on the dashboard. One row per meaningful user action (question
    # generation, grading, faculty override, exam publish) - read back
    # chronologically by GET /api/activity.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT,
            subject TEXT,
            type TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Exams/published question papers, persisted instead of the old
    # in-memory-only MOCK_EXAMS list (which reset on every server restart).
    # question_ids is stored as a JSON array string. Used to derive real
    # CO attainment trend / CO-PO correlation data from what's actually
    # been published, instead of static placeholder charts.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            subject TEXT,
            total_marks INTEGER,
            duration INTEGER,
            question_ids TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

QUESTION_COLUMNS = [
    "id", "text", "type", "subject", "unit", "bloom_level", "bloom_label",
    "co", "po", "marks", "difficulty", "answer_key", "source_chunk",
    "generation_explanation", "answer_key_explanation", "sha256", "created_at",
]

def question_sha256(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()

def is_duplicate(sha: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT 1 FROM questions WHERE sha256 = ?", (sha,)).fetchone()
    except sqlite3.OperationalError:
        # Table doesn't exist yet (e.g. brand-new DB) - nothing to be a duplicate of.
        conn.close()
        init_db()
        return False
    conn.close()
    return row is not None

def save_question(q: dict):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO questions
            (id, text, type, subject, unit, bloom_level, bloom_label, co, po,
             marks, difficulty, answer_key, source_chunk,
             generation_explanation, answer_key_explanation, sha256, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            q["id"], q["text"], q["type"], q["subject"], q["unit"],
            q["bloom_level"], q["bloom_label"], q["co"], q["po"],
            q["marks"], q["difficulty"], q.get("answer_key"),
            q.get("source_chunk"), q.get("generation_explanation"),
            q.get("answer_key_explanation"), q["sha256"], q["created_at"]
        ))
        conn.commit()
    finally:
        conn.close()

def update_question_fields(qid: str, fields: dict):
    """Updates arbitrary columns on an existing question row (e.g. faculty-
    specified marks override, or explanations added after initial save)."""
    if not fields:
        return
    allowed = {k: v for k, v in fields.items() if k in QUESTION_COLUMNS and k != "id"}
    if not allowed:
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in allowed)
        conn.execute(f"UPDATE questions SET {set_clause} WHERE id = ?", (*allowed.values(), qid))
        conn.commit()
    finally:
        conn.close()

# ── Answer schemes ──────────────────────────────────────────────────────────────

def create_answer_scheme(question: dict, question_number: Optional[int] = None) -> dict:
    """
    Creates an answer-scheme row for a question - its own id, separate from
    the question's id, holding the marks, answer key, and explanation that
    graders should reference. Returns the created scheme as a dict.
    """
    init_db()
    import uuid
    scheme = {
        "id": f"AK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        "question_id": question["id"],
        "question_text": question.get("text"),
        "question_number": question_number,
        "subject": question.get("subject"),
        "type": question.get("type"),
        "marks": question.get("marks"),
        "answer_key": question.get("answer_key"),
        "explanation": question.get("answer_key_explanation"),
        "created_at": datetime.now().isoformat(),
    }
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO answer_schemes
            (id, question_id, question_text, question_number, subject, type, marks, answer_key, explanation, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            scheme["id"], scheme["question_id"], scheme["question_text"], scheme["question_number"],
            scheme["subject"], scheme["type"], scheme["marks"], scheme["answer_key"],
            scheme["explanation"], scheme["created_at"],
        ))
        conn.commit()
    finally:
        conn.close()
    return scheme

def get_answer_schemes(question_id: Optional[str] = None, subject: Optional[str] = None) -> List[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM answer_schemes WHERE 1=1"
    params = []
    if question_id:
        query += " AND question_id = ?"
        params.append(question_id)
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_answer_scheme_by_id(answer_id: str) -> Optional[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM answer_schemes WHERE id = ?", (answer_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_answer_scheme_by_question_id(question_id: str) -> Optional[dict]:
    schemes = get_answer_schemes(question_id=question_id)
    return schemes[0] if schemes else None

def get_all_questions(subject=None, unit=None, bloom_level=None, q_type=None):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    return [dict(r) for r in rows]

def get_question_by_id(qid: str) -> Optional[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)

def delete_question(qid: str):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()

# ── Activity log ─────────────────────────────────────────────────────────────
# Backs the dashboard's "Recent Activity" panel with real events instead of
# a hardcoded list. Call log_activity() at the point an action actually
# happens (generation, grading, override, exam publish) - this module is
# the single place new action types should be added.

def log_activity(action: str, activity_type: str, detail: str = "", subject: str = ""):
    """
    action: short human-readable description, e.g. "Generated 3 questions"
    activity_type: one of "generate" | "grade" | "override" | "publish"
      (matches the color-coding the dashboard UI already uses)
    detail/subject: optional extra context shown under the action line
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO activity_log (action, detail, subject, type, created_at) VALUES (?, ?, ?, ?, ?)",
        (action, detail, subject, activity_type, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def get_recent_activity(limit: int = 10) -> List[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Exams (published question papers) ───────────────────────────────────────
# Persisted instead of the old in-memory-only mock list, so exam history -
# and therefore CO attainment trend / CO-PO correlation derived from it -
# survives a server restart and reflects what's actually been published.

def save_exam(exam: dict):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO exams (id, title, subject, total_marks, duration, question_ids, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (exam["id"], exam["title"], exam.get("subject", ""), exam.get("total_marks", 0),
         exam.get("duration", 0), json.dumps(exam.get("question_ids", [])),
         exam.get("status", "draft"), exam.get("created_at") or datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def get_exams() -> List[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM exams ORDER BY created_at ASC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["question_ids"] = json.loads(d["question_ids"]) if d.get("question_ids") else []
        out.append(d)
    return out

def get_exam_by_id(exam_id: str) -> Optional[dict]:
    for e in get_exams():
        if e["id"] == exam_id:
            return e
    return None

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
    marks: Optional[int]
    context_chunks: List[str]
    raw_questions: List[str]
    validated_questions: List[str]
    tagged_questions: List[dict]
    final_questions: List[dict]
    errors: List[str]
    # Human-readable reasons for why fewer than `count` questions came out
    # the other end - one entry per question dropped by a filtering step
    # (quality/difficulty/correctness validators or sha256 dedup). Lets
    # callers report a precise cause instead of a generic "fewer than
    # requested" message.
    drop_reasons: List[str]

# ── LLM call helper ───────────────────────────────────────────────────────────
#
# Tuned for small/local models (e.g. Ollama mistral 7B): low temperature makes
# JSON-structured and grading-adjacent output far more consistent than the
# Ollama default (~0.8), which otherwise gives noticeably different answer
# keys / explanations / scores on repeated runs of the same question.

def llm_call(prompt: str, model: str = None, temperature: float = 0.2) -> str:
    if not OLLAMA_AVAILABLE:
        return ""
    model = model or os.getenv("OLLAMA_MODEL", "mistral")
    try:
        resp = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
        )
        return resp["message"]["content"]
    except Exception:
        return ""

def extract_json_block(text: str) -> Optional[str]:
    """
    Robustly pulls a JSON object out of an LLM response. Small local models
    (e.g. Mistral 7B) frequently wrap JSON in ```json ... ``` fences or add
    a sentence of preamble/trailing commentary - a naive `\\{.*\\}` regex can
    grab the wrong span when that happens. This strips fences and then
    brace-matches from the first '{' to its true closing '}'.
    """
    if not text:
        return None
    cleaned = re.sub(r'```(?:json)?', '', text).strip()
    start = cleaned.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == '{':
            depth += 1
        elif cleaned[i] == '}':
            depth -= 1
            if depth == 0:
                return cleaned[start:i + 1]
    return None

def parse_llm_json(text: str) -> Optional[dict]:
    block = extract_json_block(text)
    if not block:
        return None
    try:
        return json.loads(block)
    except Exception:
        return None

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

Output ONLY a numbered list of questions. No preamble, no explanations, no
question labels or brackets - just the number, a period, and the question
text itself.
1. Explain how X relates to Y in this context.
2. Calculate the value of Z given the following conditions...
..."""

    raw = llm_call(prompt, temperature=0.7)
    questions = []
    if raw:
        for line in raw.strip().split("\n"):
            line = line.strip()
            match = re.match(r"^\d+[\.\)]\s*(.+)", line)
            if match:
                q = match.group(1).strip()
                # Defensively strip a leading "[Question N]"/"[Q1]"-style
                # label some LLMs echo despite the prompt no longer showing
                # one as an example - this is noise, not a real unfilled
                # template placeholder, and was previously causing
                # correctness_validator_agent to wrongly reject otherwise-
                # complete questions just for containing a leading "[".
                q = re.sub(r"^\[\s*Q(?:uestion)?\.?\s*\d+\s*\]\s*", "", q, flags=re.IGNORECASE).strip()
                if len(q) > 20:
                    questions.append(q)

    reasons = list(state.get("drop_reasons", []))
    if len(questions) < state["count"]:
        shortfall = state["count"] - len(questions)
        reasons.append(
            f"Generator (LLM) only returned {len(questions)}/{state['count']} usable question(s) "
            f"in its response for this Bloom level/CO/subject combination - {shortfall} slot(s) "
            f"could not be filled at this step."
        )
    state["raw_questions"] = questions
    state["drop_reasons"] = reasons
    return state

def quality_validator_agent(state: PipelineState) -> PipelineState:
    """Checks question quality: length, clarity, specificity."""
    validated = []
    reasons = list(state.get("drop_reasons", []))
    for q in state["raw_questions"]:
        if len(q) < 20:
            reasons.append(f'QualityValidator dropped "{q[:60]}..." - too short (under 20 characters).')
            continue
        # Must end with ? or have directive verb
        has_question_form = "?" in q or any(
            q.lower().startswith(v) for v in ["derive", "calculate", "find", "draw", "explain",
                "describe", "analyze", "evaluate", "design", "state", "prove", "determine"]
        )
        if has_question_form:
            validated.append(q)
        else:
            reasons.append(
                f'QualityValidator dropped "{q[:60]}..." - doesn\'t read as a question '
                f"(no \"?\" and doesn't start with a directive verb like Explain/Calculate/Derive)."
            )
    # If filtering would wipe out everything, keep the raw list instead (and
    # drop the reasons we just logged for it, since nothing was actually lost).
    if not validated and state["raw_questions"]:
        validated = state["raw_questions"]
        reasons = list(state.get("drop_reasons", []))
    state["validated_questions"] = validated
    state["drop_reasons"] = reasons
    return state

def difficulty_validator_agent(state: PipelineState) -> PipelineState:
    """Confirms difficulty aligns with Bloom level — filters trivially easy questions for high levels."""
    bloom = state["bloom_level"]
    if bloom <= 2:
        return state  # any question fine for low levels
    filtered = []
    reasons = list(state.get("drop_reasons", []))
    for q in state["validated_questions"]:
        word_count = len(q.split())
        # High Bloom levels should have substantive questions
        if bloom >= 4 and word_count < 10:
            reasons.append(
                f'DifficultyValidator dropped "{q[:60]}..." - only {word_count} words, '
                f"too brief/trivial for Bloom L{bloom}."
            )
            continue
        filtered.append(q)
    if not filtered and state["validated_questions"]:
        filtered = state["validated_questions"]
        reasons = list(state.get("drop_reasons", []))
    state["validated_questions"] = filtered
    state["drop_reasons"] = reasons
    return state

def correctness_validator_agent(state: PipelineState) -> PipelineState:
    """Checks that question text doesn't contain contradictions or obvious errors."""
    # Heuristic: remove questions that still contain an unfilled template
    # placeholder. Deliberately narrower than "any '[' character" - that
    # used to also reject perfectly good questions that happened to start
    # with an echoed "[Question N]" label (a generator_agent prompt-format
    # issue, fixed separately) or that legitimately use brackets for units
    # (e.g. "[kJ/kg]") or references. A real unfilled placeholder reads like
    # "[topic]", "[insert value here]", "[X]" - a short, lowercase-ish
    # bracketed token standing in for content, not a number/unit/label.
    placeholder_pattern = re.compile(r"\[\s*(?:[a-zA-Z][a-zA-Z \-]{0,30})\s*\]")
    filtered = []
    reasons = list(state.get("drop_reasons", []))
    for q in state["validated_questions"]:
        has_blank_run = "___" in q
        placeholder_match = placeholder_pattern.search(q)
        # Exclude bracketed content that's actually numeric/units (e.g.
        # "[kJ/kg]", "[50mm]") - those aren't unfilled placeholders.
        is_real_placeholder = placeholder_match and not re.search(r"\d", placeholder_match.group(0))
        if has_blank_run or is_real_placeholder:
            reasons.append(
                f'CorrectnessValidator dropped "{q[:60]}..." - still contains an unfilled '
                f"template placeholder (\"[...]\" or \"___\")."
            )
            continue
        filtered.append(q)
    if not filtered and state["validated_questions"]:
        filtered = state["validated_questions"]
        reasons = list(state.get("drop_reasons", []))
    state["validated_questions"] = filtered
    state["drop_reasons"] = reasons
    return state

def pedagogy_tagger_agent(state: PipelineState) -> PipelineState:
    """Tags each question with CO/PO mapping, marks, difficulty, Bloom label."""
    bloom_label = BLOOM_LABELS[state["bloom_level"]][0]
    # Raw-data context this whole batch of questions was generated from -
    # stored per-question so grading can later reference exactly what was
    # used to write the question (no separate per-question retrieval needed).
    source_chunk = "\n\n".join(state["context_chunks"])[:3000]
    # Marks: honor whatever the faculty member typed in the form if given;
    # only fall back to the fixed Bloom->marks table when no explicit value
    # was requested. Previously this ALWAYS used the table, silently
    # overwriting the user's "Marks per Q" input (e.g. typing 10 for an L3
    # question always produced 8 marks, since MARKS_BY_BLOOM[3] == 8).
    marks = state.get("marks") or MARKS_BY_BLOOM[state["bloom_level"]]
    tagged = []
    reasons = list(state.get("drop_reasons", []))
    import uuid
    for i, q_text in enumerate(state["validated_questions"]):
        sha = question_sha256(q_text)
        if is_duplicate(sha):
            reasons.append(
                f'PedagogyTagger dropped "{q_text[:60]}..." - an identical question '
                f"already exists in the question bank (sha256 duplicate)."
            )
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
            "marks": marks,
            "difficulty": DIFFICULTY_BY_BLOOM[state["bloom_level"]],
            "source_chunk": source_chunk,
            "sha256": sha,
            "created_at": datetime.now().isoformat(),
        })
    state["tagged_questions"] = tagged
    state["drop_reasons"] = reasons
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

def provenance_explainer_agent(state: PipelineState) -> PipelineState:
    """
    Step 1 'validation' requirement: explains, for each approved question,
    WHY and WHERE it was generated from - which subject/chapter, which
    Bloom level/CO it targets, and an excerpt of the actual source text it
    is grounded in. Fully deterministic/templated (no LLM dependency), so
    it's always available even without Ollama running.
    """
    bloom_label, bloom_verbs = BLOOM_LABELS[state["bloom_level"]]
    for q in state["final_questions"]:
        source_chunk = q.get("source_chunk", "") or ""
        excerpt = source_chunk[:280].strip()
        if len(source_chunk) > 280:
            excerpt += "..."

        if excerpt:
            grounding = f'It was generated from the following passage in the raw data for "{q["unit"]}": "{excerpt}"'
        else:
            grounding = (
                "No matching passage was retrieved from the raw data for this chapter, "
                "so this question was produced from a generic template instead - treat it "
                "as lower-confidence and review before use."
            )

        q["generation_explanation"] = (
            f'This question was generated for {q["subject"]} → "{q["unit"]}", targeting '
            f'Bloom\'s Level {q["bloom_level"]} ({bloom_label} - {bloom_verbs}) under {q["co"]}. '
            f"{grounding}"
        )
    return state

def answer_key_agent(state: PipelineState) -> PipelineState:
    """
    Writes a model/reference answer for each approved question, grounded
    strictly in its source_chunk (the raw data retrieved for it), plus an
    explanation of why that answer is correct and which part of the source
    material it comes from (Step 2 requirement). This answer_key becomes
    the reference text the grading system later compares student answers
    against (keyword + semantic matching).
    """
    for q in state["final_questions"]:
        source_chunk = q.get("source_chunk", "")
        if not source_chunk:
            q["answer_key"] = ""
            q["answer_key_explanation"] = (
                "No source data was available for this question, so no grounded "
                "answer key could be written - grading will fall back to a reduced reference."
            )
            continue

        if not OLLAMA_AVAILABLE:
            # No LLM available - fall back to using the raw chunk itself as the
            # reference text. Less polished, but keyword/semantic matching
            # still works since it's still raw-data-derived.
            q["answer_key"] = source_chunk
            q["answer_key_explanation"] = (
                "LLM unavailable, so the raw source passage itself is used directly as the "
                "reference answer (no paraphrasing/explanation was generated)."
            )
            continue

        prompt = f"""You are an expert {q['subject']} professor.
Using ONLY the source material below, write a model answer for the exam
question, AND explain why it is correct / which part of the source material
it is grounded in.

QUESTION: {q['text']}

SOURCE MATERIAL:
{source_chunk}

Respond with ONLY a JSON object in exactly this format - no markdown code
fences, no preamble, no text before or after the JSON:
{{"answer_key": "<4-8 sentence model answer, using only facts from the source material>", "explanation": "<2-3 sentences: why this is the correct answer and which part of the source material it draws from>"}}"""

        raw = llm_call(prompt, temperature=0.2)
        parsed = parse_llm_json(raw)
        if not parsed:
            # Small models occasionally ignore formatting instructions on the
            # first try - one retry with a blunter reminder is cheap and
            # noticeably improves the success rate for 7B-class models.
            retry_prompt = prompt + "\n\nIMPORTANT: Output raw JSON only. Do not use ```json fences."
            raw = llm_call(retry_prompt, temperature=0.1)
            parsed = parse_llm_json(raw)

        answer_key = parsed.get("answer_key") if parsed else None
        explanation = parsed.get("explanation") if parsed else None
        q["answer_key"] = (answer_key or raw or source_chunk).strip()
        q["answer_key_explanation"] = (explanation or
            "Generated from the source material retrieved for this question's chapter.").strip()
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
    graph.add_node("provenance_explainer", provenance_explainer_agent)
    graph.add_node("answer_key", answer_key_agent)
    graph.add_node("archivist", archivist_agent)

    graph.set_entry_point("bloom_analyzer")
    graph.add_edge("bloom_analyzer", "scout")
    graph.add_edge("scout", "generator")
    graph.add_edge("generator", "quality_validator")
    graph.add_edge("quality_validator", "difficulty_validator")
    graph.add_edge("difficulty_validator", "correctness_validator")
    graph.add_edge("correctness_validator", "pedagogy_tagger")
    graph.add_edge("pedagogy_tagger", "syllabus_guardian")
    graph.add_edge("syllabus_guardian", "provenance_explainer")
    graph.add_edge("provenance_explainer", "answer_key")
    graph.add_edge("answer_key", "archivist")
    graph.add_edge("archivist", END)

    return graph.compile()

# ── Public API ─────────────────────────────────────────────────────────────────

_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline

def run_pipeline_with_diagnostics(subject: str, unit: str, bloom_level: int, question_type: str,
                                   co: str, count: int = 4, marks: Optional[int] = None
                                   ) -> "tuple[List[dict], List[str]]":
    """
    Same generation as run_pipeline(), but also returns the list of
    human-readable reasons (if any) for why fewer than `count` questions
    came out the other end - e.g. the LLM under-producing, a validator
    rejecting a question, or sha256 dedup against an existing question.

    `marks` is optional: when given, every returned question is tagged with
    this exact marks value instead of the fixed Bloom-level->marks table
    (MARKS_BY_BLOOM), so the faculty member's "Marks per Q" input is
    actually honored.
    """
    init_db()

    initial_state: PipelineState = {
        "subject": subject,
        "unit": unit,
        "bloom_level": bloom_level,
        "question_type": question_type,
        "co": co,
        "count": count,
        "marks": marks,
        "context_chunks": [],
        "raw_questions": [],
        "validated_questions": [],
        "tagged_questions": [],
        "final_questions": [],
        "errors": [],
        "drop_reasons": [],
    }

    pipeline = get_pipeline()
    if pipeline and OLLAMA_AVAILABLE:
        try:
            result = pipeline.invoke(initial_state)
            if result["final_questions"]:
                return result["final_questions"], result.get("drop_reasons", [])
        except Exception:
            pass

    # Fallback: run agents manually without LangGraph
    state = initial_state
    for agent in [bloom_analyzer_agent, scout_agent, generator_agent,
                  quality_validator_agent, difficulty_validator_agent,
                  correctness_validator_agent, pedagogy_tagger_agent,
                  syllabus_guardian_agent, provenance_explainer_agent,
                  answer_key_agent, archivist_agent]:
        state = agent(state)

    if state["final_questions"]:
        return state["final_questions"], state.get("drop_reasons", [])

    # Total fallback (no LLM/LangGraph at all): mock questions are always
    # fully synthetic placeholders, never short of `count`, so no drop
    # reasons apply here - but they're clearly unconnected to real source
    # data, which the caller can still flag via the `source` field.
    return _mock_questions(subject, unit, bloom_level, question_type, co, count, marks=marks), []


def run_pipeline(subject: str, unit: str, bloom_level: int, question_type: str,
                 co: str, count: int = 4, marks: Optional[int] = None) -> List[dict]:
    """
    Main entry point. Returns list of generated question dicts.
    Falls back to mock questions if LangGraph or Ollama unavailable.

    Thin backward-compatible wrapper around run_pipeline_with_diagnostics()
    for callers that only need the questions, not the shortfall reasons.
    """
    questions, _ = run_pipeline_with_diagnostics(
        subject=subject, unit=unit, bloom_level=bloom_level,
        question_type=question_type, co=co, count=count, marks=marks,
    )
    return questions

def _mock_questions(subject, unit, bloom_level, q_type, co, count, marks: Optional[int] = None) -> List[dict]:
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
    for i in range(count):
        base_text = texts[i % len(texts)]
        text = base_text if i < len(texts) else f"{base_text} (variant {i // len(texts) + 1})"
        q_id = f"Q-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        # Hash on id (always unique) rather than text alone - text is templated
        # and will legitimately repeat across separate mock-fallback calls;
        # we still want every returned question to actually persist to the DB.
        sha = question_sha256(f"{text}-{q_id}")
        q = {
            "id": q_id,
            "text": text,
            "type": q_type,
            "subject": subject,
            "unit": unit,
            "bloom_level": bloom_level,
            "bloom_label": bloom_label,
            "co": co,
            "po": CO_PO_MAP.get(co, "PO1"),
            "marks": marks or MARKS_BY_BLOOM.get(bloom_level, 8),
            "difficulty": DIFFICULTY_BY_BLOOM.get(bloom_level, "medium"),
            "answer_key": "",
            "source_chunk": "",
            "generation_explanation": (
                f"No raw data / LLM pipeline was available, so this question was produced "
                f"from a generic {q_type} template for {subject} → \"{unit}\" rather than being "
                f"grounded in retrieved source material. Treat as a placeholder for review."
            ),
            "answer_key_explanation": (
                "No source data was available, so no grounded answer key could be generated."
            ),
            "sha256": sha,
            "created_at": datetime.now().isoformat(),
        }
        if not is_duplicate(sha):
            save_question(q)
        questions.append(q)
    return questions

def run_pipeline_for_specs(subject: str, unit: str, question_type: str,
                            specs: List[dict]) -> "tuple[List[dict], dict[int, str]]":
    """
    Step 1+2 entry point: generates one question per item in `specs`, where
    each spec is {"bloom_level": int, "co": str, "marks": int} - i.e. the
    faculty chooses Bloom level, CO, and marks individually per question,
    plus the shared subject/chapter/question_type for the whole batch.

    Internally groups specs that share the same (bloom_level, co) into a
    single underlying generation run - NOT also grouped by marks, since
    marks doesn't affect what gets generated/retrieved, only how the
    result is tagged afterward. Grouping by marks too would split one
    Bloom/CO batch into several separate LLM generation runs whenever
    marks differ row-to-row (e.g. 4 questions all at L3/CO1 but with
    different marks each), multiplying LLM round-trips for no benefit.
    Each spec's own `marks` is instead applied as a fast post-hoc override
    after generation (no extra LLM call).

    Returns (questions, drop_reasons):
      - questions: one dict per spec that successfully generated, in the
        original requested order (a spec's slot is omitted only if
        generation/dedup yielded fewer questions than requested for its
        group).
      - drop_reasons: {spec_index: reason} for every omitted slot, so
        callers can tell the user exactly why each missing question is
        missing instead of a generic shortfall count.
    """
    from collections import defaultdict

    groups = defaultdict(list)  # (bloom_level, co) -> [spec_index, ...]
    for idx, spec in enumerate(specs):
        groups[(spec["bloom_level"], spec["co"])].append(idx)

    results_by_index: dict = {}
    drop_reasons_by_index: dict = {}
    for (bloom_level, co), indices in groups.items():
        generated, reasons = run_pipeline_with_diagnostics(
            subject=subject, unit=unit, bloom_level=bloom_level,
            question_type=question_type, co=co, count=len(indices),
        )
        for idx, q in zip(indices, generated):
            requested_marks = specs[idx].get("marks")
            if requested_marks and q.get("marks") != requested_marks:
                q["marks"] = requested_marks
                try:
                    update_question_fields(q["id"], {"marks": requested_marks})
                except Exception:
                    pass
            results_by_index[idx] = q
        # Any indices in this group beyond len(generated) didn't get a
        # question - attribute the group's collected drop reasons to them
        # (best-effort: we know WHY the group came up short, just not
        # precisely which named slot a given drop corresponds to once
        # several specs share one group).
        missing_indices = indices[len(generated):]
        if missing_indices:
            reason_text = " ".join(reasons) if reasons else (
                f"Generation for Bloom L{bloom_level}/{co} yielded fewer questions than "
                f"requested, for an unspecified reason (no validator/dedup reason was logged)."
            )
            for idx in missing_indices:
                drop_reasons_by_index[idx] = reason_text

    questions = [results_by_index[i] for i in sorted(results_by_index)]
    return questions, drop_reasons_by_index
