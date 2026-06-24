
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import os


# =========================================================
# CREATE / LOAD VECTOR DATABASE
# =========================================================
def create_vector_db(
    chunks=None,
    persist_directory="./data/db/chroma"
):

    """
    Creates or loads Chroma Vector DB
    """

    # =====================================================
    # EMBEDDING MODEL
    # =====================================================
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    except Exception as e:
        if chunks is not None:
            raise
        print(f"⚠️ Embedding model failed to load ({e}), returning None — caller should use fallback retrieval")
        return None

    # =====================================================
    # COLLECTION NAME
    # =====================================================
    collection_name = os.path.basename(
        persist_directory
    ).lower()

    # Sanitize collection name for ChromaDB (only alphanumeric, dots, underscores, hyphens)
    import re
    collection_name = re.sub(r'[^a-zA-Z0-9._-]', '_', collection_name)
    collection_name = re.sub(r'_+', '_', collection_name)  # Replace multiple underscores with single
    collection_name = collection_name.strip('_')  # Remove leading/trailing underscores

    # Ensure it starts and ends with alphanumeric
    if not collection_name[0].isalnum():
        collection_name = 'db_' + collection_name
    if not collection_name[-1].isalnum():
        collection_name = collection_name + '_db'

    # =====================================================
    # CREATE DIRECTORY
    # =====================================================
    os.makedirs(
        persist_directory,
        exist_ok=True
    )

    # =====================================================
    # LOAD EXISTING DB
    # =====================================================
    if chunks is None:

        print(
            f"\n📂 Loading Vector DB: "
            f"{collection_name}"
        )

        vectordb = Chroma(
            collection_name=collection_name,
            persist_directory=persist_directory,
            embedding_function=embeddings
        )

        return vectordb

    # =====================================================
    # CREATE NEW DB
    # =====================================================
    print(
        f"\n🧠 Creating Vector DB: "
        f"{collection_name}"
    )

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=persist_directory
    )

    print("✅ Vector DB Created Successfully")

    return vectordb
