"""
Data source browser: lets faculty see (and download) the actual raw files
data/raw/<subject>/... that generation is supposed to be grounded in, plus
data/pyqs/<subject>/... previous-year question papers, and whether each
subject currently has matching ingested ChromaDB content.

This module is read-only and deliberately doesn't depend on chromadb/
langchain at all (just checks whether a non-empty collection directory
exists) - so it works even when those heavy packages aren't installed
(e.g. backend running degraded), and stays fast since it's just filesystem
+ a small SQLite row-count query.
"""

import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
PYQS_DIR = DATA_DIR / "pyqs"
CHROMA_DIR = DATA_DIR / "db" / "chroma"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".pptx"}


def _extract_unit_label(path: Path) -> str:
    """Mirrors ingestion/metadata_extractor.py's own unit-extraction regex,
    so the label shown here matches exactly what ends up in Chroma metadata."""
    text = str(path)
    match = re.search(r"Unit[_ -]?(\d+)", text, re.IGNORECASE)
    if match:
        return f"Unit {match.group(1)}"
    for part in path.parts:
        if "unit" in part.lower():
            return part.replace("_", " ")
    return "Unspecified"


def _list_files(subject_dir: Path) -> list:
    files = []
    if not subject_dir.exists():
        return files
    for p in sorted(subject_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS:
            try:
                stat = p.stat()
            except OSError:
                continue
            files.append({
                "name": p.name,
                "relativePath": str(p.relative_to(subject_dir)),
                "unit": _extract_unit_label(p),
                "sizeBytes": stat.st_size,
                "modifiedAt": int(stat.st_mtime),
            })
    return files


def _chroma_chunk_count(subject: str) -> Optional[int]:
    """Best-effort chunk count for a subject's Chroma collection, read
    directly via sqlite3 (no chromadb/langchain import needed) - returns
    None if the collection doesn't exist or can't be read, rather than
    raising, since this is purely informational."""
    sqlite_path = CHROMA_DIR / subject / "chroma.sqlite3"
    if not sqlite_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def list_subjects() -> list:
    """
    One entry per subject folder found under data/raw/ (the authoritative
    list of subjects that can actually be grounded - this is deliberately
    NOT the same as any hardcoded UI dropdown, so the two can never drift
    apart silently again).
    """
    if not RAW_DIR.exists():
        return []

    subjects = []
    for subject_dir in sorted(p for p in RAW_DIR.iterdir() if p.is_dir()):
        subject = subject_dir.name
        raw_files = _list_files(subject_dir)
        pyq_dir = PYQS_DIR / subject
        pyq_files = _list_files(pyq_dir) if pyq_dir.exists() else []
        chunk_count = _chroma_chunk_count(subject)
        units = sorted(
            {f["unit"] for f in raw_files if f["unit"] != "Unspecified"},
            key=lambda u: (len(u), u),
        )
        subjects.append({
            "subject": subject,
            "ingested": chunk_count is not None and chunk_count > 0,
            "chunkCount": chunk_count,
            "rawFileCount": len(raw_files),
            "rawSizeBytes": sum(f["sizeBytes"] for f in raw_files),
            "pyqFileCount": len(pyq_files),
            "units": units,
        })
    return subjects


def list_files_for_subject(subject: str) -> Optional[dict]:
    """Detailed raw + pyq file listing for one subject. Returns None if the
    subject doesn't exist on disk at all (caller should 404)."""
    subject_dir = RAW_DIR / subject
    pyq_dir = PYQS_DIR / subject
    if not subject_dir.exists() and not pyq_dir.exists():
        return None
    return {
        "subject": subject,
        "rawFiles": _list_files(subject_dir),
        "pyqFiles": _list_files(pyq_dir) if pyq_dir.exists() else [],
        "chunkCount": _chroma_chunk_count(subject),
    }


def resolve_file_path(subject: str, relative_path: str, source: str = "raw") -> Optional[Path]:
    """
    Safely resolves a (subject, relative_path) pair to an actual file under
    data/raw or data/pyqs, refusing anything that would escape that base
    directory (path traversal) or doesn't correspond to a real existing
    subject folder. Returns None if the request doesn't resolve to a real,
    in-bounds file - callers should treat that as 404, never re-attempt a
    looser resolution.
    """
    base_dir = RAW_DIR if source == "raw" else PYQS_DIR
    # The subject itself must be one of the real, already-discovered
    # subject folder names - never trust a caller-supplied subject path
    # segment directly without checking it against the real directory list.
    real_subjects = {p.name for p in base_dir.iterdir() if p.is_dir()} if base_dir.exists() else set()
    if subject not in real_subjects:
        return None

    subject_dir = (base_dir / subject).resolve()
    candidate = (subject_dir / relative_path).resolve()

    try:
        candidate.relative_to(subject_dir)
    except ValueError:
        return None  # relative_path attempted to escape the subject directory

    if not candidate.is_file() or candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        return None

    return candidate
