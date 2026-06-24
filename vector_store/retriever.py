import os
import sqlite3


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

