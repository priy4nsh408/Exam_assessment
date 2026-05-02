
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import os

# =========================================================
# CREATE / LOAD VECTOR DATABASE
# =========================================================
def create_vector_db(
    chunks=None,
    persist_directory="./data/db/chroma"
):
    """
    Creates or loads a Chroma Vector Database.

    Parameters:
    ---------------------------------
    chunks : list
        List of LangChain documents/chunks

    persist_directory : str
        Path where Chroma DB is stored

    Returns:
    ---------------------------------
    vectordb : Chroma object
    """

    # =====================================================
    # EMBEDDING MODEL
    # =====================================================
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # =====================================================
    # CREATE DIRECTORY IF NOT EXISTS
    # =====================================================
    os.makedirs(persist_directory, exist_ok=True)

    # =====================================================
    # LOAD EXISTING DATABASE
    # =====================================================
    if chunks is None:

        print(f"📂 Loading Vector DB from: {persist_directory}")

        vectordb = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )

        return vectordb

    # =====================================================
    # CREATE NEW DATABASE
    # =====================================================
    print(f"🧠 Creating New Vector DB at: {persist_directory}")

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory
    )

    # =====================================================
    # SAVE DATABASE
    # =====================================================
    vectordb.persist()

    print("✅ Vector DB Saved Successfully")

    return vectordb

