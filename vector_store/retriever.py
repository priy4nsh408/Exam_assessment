import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_RAW_DIR = PROJECT_ROOT / "data" / "db" / "chroma"
CHROMA_PYQ_DIR = PROJECT_ROOT / "data" / "db" / "chroma_pyq"


def retrieve_pyq_context(subject, unit=None, query="", k=5):
    """
    Retrieve PYQ/question-bank context for a subject.
    Tries vector similarity first, falls back to SQLite keyword retrieval.
    If unit-filtered retrieval returns nothing, retries without unit filter.
    """
    persist_dir = str(CHROMA_PYQ_DIR / subject)
    if not os.path.exists(persist_dir):
        for d in CHROMA_PYQ_DIR.iterdir() if CHROMA_PYQ_DIR.exists() else []:
            if d.name.lower() == subject.lower():
                persist_dir = str(d)
                break
        else:
            return ""

    try:
        from vector_store.chroma_client import create_vector_db
        vectordb = create_vector_db(chunks=None, persist_directory=persist_dir)
        if vectordb is not None:
            result = retrieve_context(
                vectordb, query=query, subject=subject, unit=unit,
                k=k, persist_directory=persist_dir
            )
            if result:
                return result
            if unit:
                return retrieve_context(
                    vectordb, query=query, subject=subject,
                    k=k, persist_directory=persist_dir
                )
            return ""
    except Exception:
        pass

    result = _fallback_keyword_retrieve(persist_dir, subject=subject, unit=unit, query=query, k=k)
    if not result and unit:
        result = _fallback_keyword_retrieve(persist_dir, subject=subject, query=query, k=k)
    return result


def retrieve_question_bank(subject, unit=None, bloom_level=None, limit=10):
    """
    Retrieve previously generated questions from the SQLite question bank
    to use as dedup reference and style examples.
    """
    db_path = PROJECT_ROOT / "data" / "questions.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT text, type, bloom_level, co, unit, marks FROM questions WHERE subject = ?"
        params = [subject]
        if unit:
            query += " AND unit LIKE ?"
            params.append(f"%{unit}%")
        if bloom_level:
            query += " AND bloom_level = ?"
            params.append(bloom_level)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def _fallback_keyword_retrieve(persist_directory, subject=None, unit=None, query="", k=5):
    """
    Direct SQLite keyword retrieval from ChromaDB's backing store.
    Used when the embedding model can't be loaded (e.g. no network
    access to HuggingFace). Less precise than vector similarity but
    returns real ingested content instead of nothing.
    """
    db_path = os.path.join(persist_directory, "chroma.sqlite3")
    if not os.path.exists(db_path):
        return ""

    conn = sqlite3.connect(db_path)
    try:
        id_conditions = []
        params = []

        if subject:
            id_conditions.append(
                "id IN (SELECT id FROM embedding_metadata WHERE key='subject' AND string_value=?)"
            )
            params.append(subject)
        if unit:
            id_conditions.append(
                "id IN (SELECT id FROM embedding_metadata WHERE key='unit' AND string_value=?)"
            )
            params.append(unit)

        where_clause = " AND ".join(id_conditions) if id_conditions else "1=1"

        sql = f"""
            SELECT string_value FROM embedding_metadata
            WHERE key='chroma:document' AND {where_clause}
            LIMIT ?
        """
        params.append(k)

        rows = conn.execute(sql, params).fetchall()
        if not rows:
            return ""

        texts = [r[0] for r in rows if r[0]]
        print(f"\n🔍 Fallback keyword retrieval: {len(texts)} chunks from SQLite")
        return "\n\n".join(texts)
    finally:
        conn.close()


def retrieve_context(
    vectordb,
    query,
    subject=None,
    unit=None,
    k=5,
    raise_on_error=False,
    persist_directory=None
):
    """
    Retrieve relevant context from ChromaDB.

    Falls back to direct SQLite keyword retrieval when the embedding
    model can't be loaded (e.g. HuggingFace is unreachable).
    """

    try:

        # =================================================
        # BUILD FILTER
        # =================================================
        if subject and unit:
            filters = {
                "$and": [
                    {"subject": {"$eq": subject}},
                    {"unit": {"$eq": unit}}
                ]
            }
        elif subject:
            filters = {"subject": {"$eq": subject}}
        elif unit:
            filters = {"unit": {"$eq": unit}}
        else:
            filters = {}

        if filters:
            print(f"🔧 Chroma where filter: {filters}")

        # =================================================
        # RETRIEVE DOCUMENTS
        # =================================================
        if filters:
            docs = vectordb.similarity_search(
                query,
                k=k,
                filter=filters
            )
        else:
            docs = vectordb.similarity_search(
                query,
                k=k
            )

        if not docs:
            print("⚠️ No matching documents found")
            return ""

        print(f"\n🔍 Retrieved {len(docs)} chunks")

        context = "\n\n".join([
            doc.page_content
            for doc in docs
        ])

        return context

    except Exception as e:

        print(f"❌ Retrieval Error: {e}")

        # Attempt fallback SQLite retrieval before giving up
        if persist_directory:
            print("⚡ Attempting fallback keyword retrieval from SQLite...")
            fallback = _fallback_keyword_retrieve(
                persist_directory, subject=subject, unit=unit, query=query, k=k
            )
            if fallback:
                return fallback

        if raise_on_error:
            raise

        return ""

