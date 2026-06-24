from langchain_core.documents import Document


def chunk_docs(docs, chunk_size_words: int = 250, chunk_overlap_words: int = 100):
    """
    Splits each document's text into overlapping WORD-based chunks (not
    LangChain's default character-based splitting). The previous
    implementation used RecursiveCharacterTextSplitter(chunk_size=500,
    chunk_overlap=100) - but those numbers are in CHARACTERS, so the real
    overlap was only ~15-20 words, not the 100 words the parameter name
    implied, and chunks could be cut mid-word at arbitrary character
    boundaries rather than on word boundaries.

    Each chunk inherits the source document's metadata (subject/unit/page/
    etc.) unchanged, so downstream retrieval filtering still works exactly
    the same way.

    chunk_size_words=250 is a reasonable paragraph-to-half-page-scale chunk
    (no specific instruction was given for chunk size, only overlap) -
    adjust here if a different chunk size is wanted.
    """
    chunks = []
    step = max(chunk_size_words - chunk_overlap_words, 1)

    for doc in docs:
        words = doc.page_content.split()
        if not words:
            continue

        if len(words) <= chunk_size_words:
            chunks.append(doc)
            continue

        for start in range(0, len(words), step):
            chunk_words = words[start:start + chunk_size_words]
            if not chunk_words:
                continue
            chunks.append(Document(
                page_content=" ".join(chunk_words),
                metadata=dict(doc.metadata),
            ))
            if start + chunk_size_words >= len(words):
                break

    return chunks
