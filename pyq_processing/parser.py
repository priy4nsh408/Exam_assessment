from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
import os


def load_pyqs(folder_path):
    docs = []

    # Extract year from folder name (e.g., ./BDT/2021 → 2021)
    year = os.path.basename(folder_path)

    for file in os.listdir(folder_path):
        path = os.path.join(folder_path, file)

        if file.endswith(".pdf"):
            loader = PyPDFLoader(path, extraction_mode="layout")  # Use layout mode for better text extraction
        elif file.endswith(".docx"):
            loader = Docx2txtLoader(path)
        else:
            continue

        loaded = loader.load()

        # Filter out poorly extracted documents
        filtered_docs = []
        for doc in loaded:
            content = doc.page_content.strip()
            
            # Skip empty documents
            if not content:
                continue
            
            # Skip documents with too many non-ASCII characters (likely OCR/garbled text)
            non_ascii_ratio = sum(1 for c in content if ord(c) > 127) / len(content) if content else 0
            if non_ascii_ratio > 0.1:  # More than 10% non-ASCII characters
                print(f"      ⚠️ Skipping PYQ {file} page {doc.metadata.get('page', 'unknown')} - appears to contain garbled/OCR text")
                continue
            
            # Skip documents that are mostly symbols/numbers without meaningful text
            alpha_ratio = sum(1 for c in content if c.isalpha()) / len(content) if content else 0
            if alpha_ratio < 0.3:  # Less than 30% alphabetic characters
                print(f"      ⚠️ Skipping PYQ {file} page {doc.metadata.get('page', 'unknown')} - insufficient readable text")
                continue
            
            filtered_docs.append(doc)

        for doc in filtered_docs:
            doc.metadata["source"] = "pyq"
            doc.metadata["file"] = file
            doc.metadata["year"] = year  # ✅ FIXED

        docs.extend(loaded)

    return docs


def load_single_pyq_file(file_path, file_name):
    """Load a single PYQ file"""
    docs = []

    if file_name.endswith(".pdf"):
        loader = PyPDFLoader(file_path, extraction_mode="layout")  # Use layout mode for better text extraction
    elif file_name.endswith(".docx"):
        loader = Docx2txtLoader(file_path)
    else:
        return docs

    loaded = loader.load()

    # Filter out poorly extracted documents
    filtered_docs = []
    for doc in loaded:
        content = doc.page_content.strip()
        
        # Skip empty documents
        if not content:
            continue
        
        # Skip documents with too many non-ASCII characters (likely OCR/garbled text)
        non_ascii_ratio = sum(1 for c in content if ord(c) > 127) / len(content) if content else 0
        if non_ascii_ratio > 0.1:  # More than 10% non-ASCII characters
            print(f"      ⚠️ Skipping PYQ {file_name} page {doc.metadata.get('page', 'unknown')} - appears to contain garbled/OCR text")
            continue
        
        # Skip documents that are mostly symbols/numbers without meaningful text
        alpha_ratio = sum(1 for c in content if c.isalpha()) / len(content) if content else 0
        if alpha_ratio < 0.3:  # Less than 30% alphabetic characters
            print(f"      ⚠️ Skipping PYQ {file_name} page {doc.metadata.get('page', 'unknown')} - insufficient readable text")
            continue
        
        filtered_docs.append(doc)

    for doc in filtered_docs:
        doc.metadata["source"] = "pyq"
        doc.metadata["file"] = file_name
        doc.metadata["year"] = "Unknown"  # Single file, no year folder

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