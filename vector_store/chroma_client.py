from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

DEFAULT_DB_PATH = "./data/db/chroma"

_embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _embeddings


def create_vector_db(chunks=None, db_path=None):
    path = db_path or DEFAULT_DB_PATH
    embeddings = get_embeddings()

    if chunks is None:
        return Chroma(
            persist_directory=path,
            embedding_function=embeddings
        )

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=path
    )
    vectordb.persist()
    return vectordb
