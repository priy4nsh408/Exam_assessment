from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

DB_PATH = "./data/db/chroma"

def create_vector_db(chunks=None):
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # 🔹 Load existing DB
    if chunks is None:
        return Chroma(
            persist_directory=DB_PATH,
            embedding_function=embeddings
        )

    # 🔹 Create new DB
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH
    )

    vectordb.persist()
    return vectordb