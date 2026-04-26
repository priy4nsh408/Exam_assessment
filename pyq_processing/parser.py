from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
import os


def load_pyqs(folder_path):
    docs = []

    # Extract year from folder name (e.g., ./BDT/2021 → 2021)
    year = os.path.basename(folder_path)

    for file in os.listdir(folder_path):
        path = os.path.join(folder_path, file)

        if file.endswith(".pdf"):
            loader = PyPDFLoader(path)
        elif file.endswith(".docx"):
            loader = Docx2txtLoader(path)
        else:
            continue

        loaded = loader.load()

        for doc in loaded:
            doc.metadata["source"] = "pyq"
            doc.metadata["file"] = file
            doc.metadata["year"] = year  # ✅ FIXED

        docs.extend(loaded)

    return docs


def extract_questions(docs):
    questions = []

    for doc in docs:
        lines = doc.page_content.split("\n")

        for line in lines:
            line = line.strip()

            # ✅ Basic cleaning
            if not line:
                continue

            # Keep only meaningful questions
            if "?" in line and len(line) > 10:
                questions.append(line)

    # ✅ Remove duplicates
    questions = list(set(questions))

    return questions