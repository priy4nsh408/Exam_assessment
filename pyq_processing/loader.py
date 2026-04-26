from langchain_community.document_loaders import PyPDFLoader
import os

def load_pyqs(folder_path):
    docs = []

    for file in os.listdir(folder_path):
        path = os.path.join(folder_path, file)

        if file.endswith(".pdf"):
            loader = PyPDFLoader(path)
        else:
            continue

        loaded_docs = loader.load()

        for doc in loaded_docs:
            doc.metadata["source"] = "pyq"
            doc.metadata["file"] = file
            doc.metadata["year"] = os.path.basename(folder_path)

        docs.extend(loaded_docs)

    return docs