"""
Ingest PYQ (Previous Year Questions) and Question Bank PDFs into ChromaDB.

Creates a separate Chroma collection per subject at:
    data/db/chroma_pyq/<subject>/

Metadata on each chunk:
    subject, unit (if extractable), source_type ("pyq"|"question_bank"),
    year (if in a year subfolder), source_file
"""

import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from chunking.chunker import chunk_docs as chunk_documents

PROJECT_ROOT = Path(__file__).parent.parent
PYQ_BASE = PROJECT_ROOT / "data" / "pyqs"
CHROMA_PYQ_DIR = PROJECT_ROOT / "data" / "db" / "chroma_pyq"


def _extract_unit_from_path(file_path: str, file_name: str) -> str:
    combined = f"{file_path}/{file_name}"
    match = re.search(r'[Uu]nit[_ -]?(\d+)', combined)
    if match:
        return f"Unit {match.group(1)}"
    return "Unknown"


def _classify_source_type(rel_path: str) -> str:
    lower = rel_path.lower()
    if "question bank" in lower or "qb" in lower or "qp" in lower:
        return "question_bank"
    return "pyq"


def _extract_year(rel_path: str) -> str:
    match = re.search(r'(20\d{2})', rel_path)
    return match.group(1) if match else "Unknown"


def load_pyq_documents(subject_path: str, subject_name: str):
    """Load all PDFs/DOCX under a subject's PYQ folder with proper metadata."""
    docs = []
    subject_path = str(subject_path)

    for root, _, files in os.walk(subject_path):
        for file in files:
            if not file.lower().endswith((".pdf", ".docx")):
                continue

            path = os.path.join(root, file)
            rel_path = os.path.relpath(root, subject_path)

            try:
                if file.lower().endswith(".pdf"):
                    loader = PyPDFLoader(path, extraction_mode="layout")
                else:
                    loader = Docx2txtLoader(path)

                loaded = loader.load()

                filtered = []
                for doc in loaded:
                    content = doc.page_content.strip()
                    if not content:
                        continue
                    non_ascii = sum(1 for c in content if ord(c) > 127) / len(content)
                    if non_ascii > 0.1:
                        continue
                    alpha = sum(1 for c in content if c.isalpha()) / len(content)
                    if alpha < 0.3:
                        continue
                    filtered.append(doc)

                for doc in filtered:
                    doc.metadata["subject"] = subject_name
                    doc.metadata["unit"] = _extract_unit_from_path(rel_path, file)
                    doc.metadata["source_type"] = _classify_source_type(rel_path)
                    doc.metadata["year"] = _extract_year(rel_path)
                    doc.metadata["source_file"] = file

                docs.extend(filtered)
                if filtered:
                    print(f"  Loaded: {file} ({len(filtered)} pages)")

            except Exception as e:
                print(f"  Failed: {file} — {e}")

    return docs


def ingest_all_pyqs():
    """Ingest PYQs for every subject found under data/pyqs/."""
    if not PYQ_BASE.exists():
        print(f"PYQ folder not found: {PYQ_BASE}")
        return

    for subject_dir in sorted(PYQ_BASE.iterdir()):
        if not subject_dir.is_dir():
            continue
        ingest_subject_pyqs(subject_dir.name)

    print("\nPYQ ingestion complete.")


def ingest_subject_pyqs(subject_name: str):
    """Ingest PYQs for a single subject. Tries ChromaDB vector store first,
    falls back to plain SQLite storage if the embedding model is unavailable."""
    subject_dir = PYQ_BASE / subject_name
    if not subject_dir.exists():
        for d in PYQ_BASE.iterdir():
            if d.name.lower() == subject_name.lower():
                subject_dir = d
                subject_name = d.name
                break
        else:
            print(f"Subject not found: {subject_name}")
            return

    print(f"\n{'='*60}")
    print(f"Ingesting PYQs for: {subject_name}")
    print(f"{'='*60}")

    docs = load_pyq_documents(subject_dir, subject_name)
    if not docs:
        print(f"  No usable documents for {subject_name}")
        return

    chunks = chunk_documents(docs)
    print(f"  Total chunks: {len(chunks)}")

    persist_dir = str(CHROMA_PYQ_DIR / subject_name)

    # Try ChromaDB vector ingestion first
    try:
        from vector_store.chroma_client import create_vector_db
        vectordb = create_vector_db(chunks=chunks, persist_directory=persist_dir)
        if vectordb is not None:
            print(f"  Stored in ChromaDB: {persist_dir}")
            print(f"  Collection count: {vectordb._collection.count()}")
            return
    except Exception as e:
        print(f"  ChromaDB ingestion failed ({e}), using SQLite fallback")

    # Fallback: store chunks directly in a SQLite DB so the fallback
    # retriever (_fallback_keyword_retrieve) can access them
    _ingest_to_sqlite(chunks, persist_dir, subject_name)


def _ingest_to_sqlite(chunks, persist_dir: str, subject_name: str):
    """Store document chunks in a SQLite DB mimicking ChromaDB's
    embedding_metadata table layout so _fallback_keyword_retrieve works."""
    os.makedirs(persist_dir, exist_ok=True)
    db_path = os.path.join(persist_dir, "chroma.sqlite3")

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_metadata (
            id INTEGER, key TEXT, string_value TEXT,
            int_value INTEGER, float_value REAL, bool_value INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_em_key ON embedding_metadata(key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_em_id ON embedding_metadata(id)")

    # Clear existing data for re-ingestion
    conn.execute("DELETE FROM embedding_metadata")

    for i, chunk in enumerate(chunks):
        meta = chunk.metadata
        rows = [
            (i, "chroma:document", chunk.page_content, None, None, None),
            (i, "subject", meta.get("subject", subject_name), None, None, None),
            (i, "unit", meta.get("unit", "Unknown"), None, None, None),
            (i, "source_type", meta.get("source_type", "pyq"), None, None, None),
            (i, "source_file", meta.get("source_file", ""), None, None, None),
            (i, "year", meta.get("year", "Unknown"), None, None, None),
        ]
        conn.executemany(
            "INSERT INTO embedding_metadata VALUES (?,?,?,?,?,?)", rows
        )

    conn.commit()
    count = conn.execute("SELECT COUNT(DISTINCT id) FROM embedding_metadata").fetchone()[0]
    conn.close()
    print(f"  Stored in SQLite fallback: {db_path}")
    print(f"  Chunk count: {count}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ingest_subject_pyqs(sys.argv[1])
    else:
        ingest_all_pyqs()
