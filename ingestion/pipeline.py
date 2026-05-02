
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import Docx2txtLoader
from langchain_community.document_loaders import UnstructuredPowerPointLoader

import os


def load_documents(base_path):

    docs = []

    if not os.path.isdir(base_path):
        print(f"❌ Invalid path: {base_path}")
        return docs

    supported_extensions = (".pdf", ".docx", ".pptx")
    base_path = os.path.normpath(base_path)
    base_name = os.path.basename(base_path)

    current_subject = None

    for root, _, files in os.walk(base_path):
        rel_root = os.path.relpath(root, base_path)
        rel_parts = [] if rel_root == "." else rel_root.split(os.sep)

        if len(rel_parts) == 0:
            subject = base_name
            unit = "Unknown"
        elif len(rel_parts) == 1:
            subject = base_name
            unit = rel_parts[0]
        else:
            subject = base_name
            unit = rel_parts[0]

        if subject != current_subject:
            print(f"\n📚 Loading Subject: {subject}")
            current_subject = subject

        if unit != "Unknown":
            print(f"   📂 Loading Unit: {unit}")

        for file in files:
            if not file.lower().endswith(supported_extensions):
                continue

            path = os.path.join(root, file)

            try:
                if file.lower().endswith(".pdf"):
                    # Use layout extraction mode for better text preservation
                    loader = PyPDFLoader(path, extraction_mode="layout")

                elif file.lower().endswith(".docx"):
                    loader = Docx2txtLoader(path)

                elif file.lower().endswith(".pptx"):
                    loader = UnstructuredPowerPointLoader(path)

                else:
                    continue

                loaded_docs = loader.load()

                # Filter out poorly extracted documents
                filtered_docs = []
                for doc in loaded_docs:
                    content = doc.page_content.strip()
                    
                    # Skip empty documents
                    if not content:
                        continue
                    
                    # Skip documents with too many non-ASCII characters (likely OCR/garbled text)
                    non_ascii_ratio = sum(1 for c in content if ord(c) > 127) / len(content) if content else 0
                    if non_ascii_ratio > 0.1:  # More than 10% non-ASCII characters
                        print(f"      ⚠️ Skipping {file} page {doc.metadata.get('page', 'unknown')} - appears to contain garbled/OCR text")
                        continue
                    
                    # Skip documents that are mostly symbols/numbers without meaningful text
                    alpha_ratio = sum(1 for c in content if c.isalpha()) / len(content) if content else 0
                    if alpha_ratio < 0.3:  # Less than 30% alphabetic characters
                        print(f"      ⚠️ Skipping {file} page {doc.metadata.get('page', 'unknown')} - insufficient readable text")
                        continue
                    
                    filtered_docs.append(doc)

                if not filtered_docs:
                    print(f"      ⚠️ No usable text extracted from {file}")
                    continue

                for doc in filtered_docs:
                    doc.metadata["subject"] = subject
                    doc.metadata["unit"] = unit
                    doc.metadata["source_file"] = file

                docs.extend(filtered_docs)
                print(f"      ✅ Loaded: {file} ({len(filtered_docs)} pages)")

            except Exception as e:
                print(f"      ❌ Failed: {file}")
                print(f"         Error: {e}")

    print(f"\n✅ TOTAL DOCUMENTS LOADED: {len(docs)}")

    return docs
