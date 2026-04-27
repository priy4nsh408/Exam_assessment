import os
import re
import random
import time

from ingestion.pipeline import load_documents
from ingestion.metadata_extractor import enrich_metadata
from chunking.chunker import chunk_docs
from vector_store.chroma_client import create_vector_db
from vector_store.retriever import retrieve_context
from generation.generator import generate_question
from tagging.hybrid_mapper import validate_question
from pyq_processing.parser import load_pyqs, extract_questions
from database.db import save_question

BT_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
CO_OPTIONS = ["CO1", "CO2", "CO3", "CO4", "CO5"]

MARKS_BY_BT = {
    "Remember": 2,
    "Understand": 2,
    "Apply": 5,
    "Analyze": 5,
    "Evaluate": 10,
    "Create": 10,
}

RAW_DATA_PATH = "./data/raw"
PYQ_DATA_PATH = "./data/pyqs"
DB_BASE_PATH = "./data/db"


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def get_available_subjects():
    if not os.path.exists(RAW_DATA_PATH):
        return []
    return sorted([
        d for d in os.listdir(RAW_DATA_PATH)
        if os.path.isdir(os.path.join(RAW_DATA_PATH, d))
    ])


def get_available_units(subject):
    subject_path = os.path.join(RAW_DATA_PATH, subject)
    if not os.path.exists(subject_path):
        return []
    units = set()
    for fname in os.listdir(subject_path):
        match = re.search(r'[Uu]nit[- ]?(\d+)', fname)
        if match:
            units.add(f"Unit {match.group(1)}")
    return sorted(units, key=lambda u: int(u.split()[-1]))


def get_available_pyq_years(subject):
    pyq_path = os.path.join(PYQ_DATA_PATH, subject)
    if not os.path.exists(pyq_path):
        return []
    return sorted([
        d for d in os.listdir(pyq_path)
        if os.path.isdir(os.path.join(pyq_path, d))
    ])


def is_subject_indexed(subject):
    db_path = os.path.join(DB_BASE_PATH, subject, "chroma")
    return os.path.exists(db_path)


# ---------------------------------------------------------------------------
# Vector DB management
# ---------------------------------------------------------------------------

def setup_subject(subject, progress_callback=None):
    """Build (or rebuild) the ChromaDB index for a subject."""
    doc_path = os.path.join(RAW_DATA_PATH, subject)
    db_path = os.path.join(DB_BASE_PATH, subject, "chroma")

    _cb(progress_callback, 0.05, "Loading documents...")
    docs = load_documents(doc_path)
    if not docs:
        raise ValueError(f"No documents found in {doc_path}")

    _cb(progress_callback, 0.25, f"Loaded {len(docs)} pages. Enriching metadata...")
    docs = enrich_metadata(docs, subject)

    _cb(progress_callback, 0.45, "Chunking documents...")
    chunks = chunk_docs(docs)

    _cb(progress_callback, 0.65, f"Embedding {len(chunks)} chunks into vector DB...")
    vectordb = create_vector_db(chunks, db_path)

    _cb(progress_callback, 1.0, "Vector database ready!")
    return vectordb


def load_subject_db(subject):
    """Load an already-indexed subject's ChromaDB. Returns None if not indexed."""
    db_path = os.path.join(DB_BASE_PATH, subject, "chroma")
    if not os.path.exists(db_path):
        return None
    return create_vector_db(None, db_path)


def get_retrieval_context(vectordb, subject, unit):
    """Build a dynamic retrieval query and return top-3 chunks as a string."""
    query = f"{subject} {unit} concepts principles"
    try:
        context = retrieve_context(vectordb, query)
        if context and context.strip():
            return context
    except Exception:
        pass
    return f"Explain key concepts and principles from {unit} of {subject}."


# ---------------------------------------------------------------------------
# PYQ helpers
# ---------------------------------------------------------------------------

def load_pyqs_for_subject(subject, year=None):
    """Load PYQs for a subject (optionally filtered by year)."""
    base = os.path.join(PYQ_DATA_PATH, subject)
    if not os.path.exists(base):
        return []

    years_to_load = [year] if year else [
        d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))
    ]

    all_pyqs = []
    for y in years_to_load:
        year_path = os.path.join(base, y)
        if not os.path.exists(year_path):
            continue
        docs = load_pyqs(year_path)
        questions = extract_questions(docs)
        for q in questions:
            all_pyqs.append({"question": q, "bt": "Understand", "co": "CO1", "unit": "Unit 1", "year": y})

    return all_pyqs


# ---------------------------------------------------------------------------
# Core generation pipeline
# ---------------------------------------------------------------------------

def run_generation(
    subject,
    selected_units,
    selected_bt,
    selected_co,
    num_questions,
    marks_override=None,
    pyq_year=None,
    progress_callback=None,
):
    """
    Generate questions for a subject and save each to the question bank.

    Yields one result dict per question so the caller can stream updates to the UI.
    """
    vectordb = load_subject_db(subject)
    if vectordb is None:
        _cb(progress_callback, 0.0, "Building vector DB (first time)...")
        vectordb = setup_subject(subject, progress_callback)

    pyqs = load_pyqs_for_subject(subject, pyq_year)
    example = random.choice(pyqs) if pyqs else {
        "question": "Explain the concept with suitable examples and diagrams."
    }

    for i in range(num_questions):
        bt = selected_bt[i % len(selected_bt)]
        co = selected_co[i % len(selected_co)]
        unit = selected_units[i % len(selected_units)] if selected_units else "Unit 1"
        marks = marks_override if marks_override else MARKS_BY_BT.get(bt, 5)

        _cb(progress_callback, i / num_questions,
            f"Question {i + 1}/{num_questions} — {bt} | {co} | {unit}")

        context = get_retrieval_context(vectordb, subject, unit)

        question = None
        validation = None
        passed = False

        for attempt in range(3):
            question = generate_question(context, example, bt, co)
            validation = validate_question(question, bt, co)
            if "Yes" in validation:
                passed = True
                break
            time.sleep(1)

        qid = save_question(subject, unit, question, bt, co, marks, validation)

        yield {
            "id": qid,
            "number": i + 1,
            "subject": subject,
            "unit": unit,
            "question": question,
            "bloom_level": bt,
            "course_outcome": co,
            "marks": marks,
            "validation": validation,
            "passed": passed,
        }

        time.sleep(0.3)

    _cb(progress_callback, 1.0, f"Done — {num_questions} questions generated and saved.")


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _cb(fn, progress, message):
    if fn:
        fn(progress, message)
